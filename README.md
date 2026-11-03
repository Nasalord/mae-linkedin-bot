# Mae LinkedIn drafter

Drafts LinkedIn posts in Vivian Liu's voice for Mae - Making Auto Easy. It runs on the reviewer's existing Claude plan: no API key and no hosting bill.

- `CLAUDE.md` tells Claude that this repo is the drafter, not a coding project.
- `prompts/drafter.md` holds Mae's pitch, Vivian's voice rules, the "never invent facts" rule, and the draft → edits → ✅ → final loop.
- `prompts/style-guide.md` is the analysis of 66 of Vivian's posts.

To change how it writes, edit those two prompt files.

## Use it from Slack (Claude in Slack app)
When Claude asks which repository to use, pick **mae-linkedin-bot**. Then DM it a topic, reply in the thread with edits, and send ✅ for the final version.

## Use it in the Claude app (claude.ai Project)
Create a Project, paste `prompts/drafter.md` into its instructions, and add `prompts/style-guide.md` as a file. Chat there.

`optional-api-bot/` is a standalone Slack bot that isn't in use, because it needs paid API usage.
