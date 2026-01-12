station chief is a tool for managing how cli harness-driven coding agents are deployed in the field. the challenge is that we use multiple harnesses (claude, codex, opencode, gemini, etc) across multiple machines and environments. some instructions are installed global to the envrionment, some are local to a project. each harness has established best practices for how they should be managed/guided, and the space is evolving fast, as new features land quickly and different companies strive toward some amount of feature parity.

there's also a cottage industry of repos and advice as people discover techniques and capabilities of these systems. there's also folks who develop and identify system prompts for various systems.

some harnesses, like claude code, increasingly want to make it easy for users to install extensions directly from a marketplace. we should be able to see what's available there.

in addition, there are various MCP directories and the ability to load MCP into projects (and globally). since MCP can pollute the context window, i'd like to keep track of any projects that have MCPs enabled to avoid bloat.

in a project, some files like AGENT.md, AGENTS.md, CLAUDE.md etc become starting points for various apps/extensions to communicate their intentions and expectations.

as a user, i want to see what's in my various global harness configs. i want to register projects to understand what instructions exist at a project level. (this can be tracking github repos or registering local project directories; a "project" could track both). i want to translate instructions for different harnesses. 

i want station chief to keep track of different repos containing skills/etc collections to see how they evolve and what we can use and learn about best practices. i want to feed it papers, blog posts, etc that describe real-world experiences and have it augment its understanding about best practices.

when creating a dev env in something like docker, i want to make it easy to pull in some kind of skills recipe so the embedded enviroment can run harnesses with capabilities in a predictable way. we could think about versioning these.

success involves having a cli that makes these tasks easy and scriptable, and a web interface that promotes observability.

i know there are others building similar things so let's search for those and learn about how they're structured and what feedback they've gotten, so we can use that to influence our system design.
