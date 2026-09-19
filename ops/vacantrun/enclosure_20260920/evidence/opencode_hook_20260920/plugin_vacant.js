// Vacant 掛鉤契約 vacant-hook/1 —— 只紀錄，不擋（見 hookcli.py 誠實邊界 2）。
// 它把 OpenCode 的事件轉成一次 `python -m vacant_network.vrun.hookcli <event>`。
import { spawnSync } from "node:child_process";

const PY = "/usr/bin/python3";
const ARGS = ["-m", "vacant_network.vrun.hookcli"];

function fire(event, payload) {
  try {
    spawnSync(PY, [...ARGS, event], {
      input: JSON.stringify(payload || {}),
      timeout: 10000, stdio: ["pipe", "ignore", "ignore"],
    });
  } catch (e) { /* 掛鉤壞掉不可以弄死 agent（誠實邊界 3） */ }
}

export const VacantHook = async () => {
  fire("session_start", { source: "opencode-plugin" });
  return {
    "tool.execute.before": async (input, output) => {
      fire("pre_tool_use", { tool_name: input && input.tool,
                             tool_input: output && output.args });
    },
    "tool.execute.after": async (input) => {
      fire("post_tool_use", { tool_name: input && input.tool });
    },
  };
};
export default VacantHook;
