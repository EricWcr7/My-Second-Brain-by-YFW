// markdown-it-texmath ships no type definitions; declare it as a markdown-it plugin.
declare module "markdown-it-texmath" {
  import type { PluginWithOptions } from "markdown-it";
  const texmath: PluginWithOptions<unknown>;
  export default texmath;
}
