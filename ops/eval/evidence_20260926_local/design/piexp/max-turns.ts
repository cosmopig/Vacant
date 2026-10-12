export default function (pi: any) {
  const maxTurns = 3;
  let completedTurns = 0;

  pi.on("before_agent_start", (event: any) => ({
    systemPrompt: `${event.systemPrompt}\n\nYou have a hard budget of ${maxTurns} model turns. Complete the task and provide your final answer within that budget.`,
  }));

  pi.on("turn_end", (_event: any, ctx: any) => {
    completedTurns += 1;
    if (completedTurns >= maxTurns) {
      ctx.abort();
    }
  });
}
