export interface ConfirmDialogOptions {
  eyebrow?: string;
  title: string;
  message: string;
  confirmLabel?: string;
  typedValue?: string;
}

export function confirmDialog(options: ConfirmDialogOptions): Promise<boolean> {
  const dialog = document.getElementById("confirm-dialog") as HTMLDialogElement;
  const form = document.getElementById("confirm-form") as HTMLFormElement;
  const eyebrow = document.getElementById("confirm-eyebrow")!;
  const title = document.getElementById("confirm-title")!;
  const message = document.getElementById("confirm-message")!;
  const typedWrap = document.getElementById("confirm-typed-wrap") as HTMLLabelElement;
  const typedLabel = document.getElementById("confirm-typed-label")!;
  const typedInput = document.getElementById("confirm-typed-input") as HTMLInputElement;
  const cancel = document.getElementById("confirm-cancel") as HTMLButtonElement;
  const submit = document.getElementById("confirm-submit") as HTMLButtonElement;
  const active = document.activeElement as HTMLElement | null;

  eyebrow.textContent = options.eyebrow || "Confirm action";
  title.textContent = options.title;
  message.textContent = options.message;
  submit.textContent = options.confirmLabel || "Delete";
  typedWrap.hidden = !options.typedValue;
  typedLabel.textContent = options.typedValue || "";
  typedInput.value = "";
  submit.disabled = Boolean(options.typedValue);

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result: boolean) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (dialog.open) dialog.close();
      active?.focus();
      resolve(result);
    };
    const onInput = () => {
      submit.disabled = typedInput.value !== options.typedValue;
    };
    const onSubmit = (event: SubmitEvent) => {
      event.preventDefault();
      if (!submit.disabled) finish(true);
    };
    const onCancel = (event: Event) => {
      event.preventDefault();
      finish(false);
    };
    const onClose = () => finish(false);
    const cleanup = () => {
      typedInput.removeEventListener("input", onInput);
      form.removeEventListener("submit", onSubmit);
      cancel.removeEventListener("click", onCancel);
      dialog.removeEventListener("cancel", onCancel);
      dialog.removeEventListener("close", onClose);
    };

    typedInput.addEventListener("input", onInput);
    form.addEventListener("submit", onSubmit);
    cancel.addEventListener("click", onCancel);
    dialog.addEventListener("cancel", onCancel);
    dialog.addEventListener("close", onClose);
    dialog.showModal();
    requestAnimationFrame(() => (options.typedValue ? typedInput : cancel).focus());
  });
}
