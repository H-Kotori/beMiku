# Working on beMiku

## Owner workflow change - 2026-10-13

The owner has superseded the self-directed handover and daily production loop. The parent assistant reviews actual Codex song studies, lyrics, and MIDI, decides the next day's direction, and updates the owner directly. Give more effort to song listening, reviewing, and learning. Instrumental generation and Vocaloid production are premature and deferred until the owner explicitly authorizes new production.

Before the next session, wait for an explicit parent-reviewed direction. Do not infer authorization from the historical handoff, roadmap dates, pending voicebank request, or old automation prompt. Preserve all existing work and evidence. See [the ready brief awaiting dispatch](docs/PARENT-REVIEW.md).

## Purpose

Learn about Hatsune Miku through creators, songs, and listeners, then create an original birthday song for August 31, 2027. The owner authorized saving project work and pushing reviewed changes to `main`. Keep work focused, incremental, and in English unless asked otherwise.

Read `README.md`, `docs/AI-HANDOFF.md`, and the latest relevant journal entry before continuing. The handoff is a short rolling note, not a transcript. Preserve user changes and inspect the working tree before editing or pulling.

## Research and listening

- Credit producers and collaborators; do not attribute their composition to the voice software.
- Prefer original uploads, artist statements, and official sources. Link the exact source and record the access date in a session entry.
- Distinguish verified facts, a creator's stated intent, a listener's interpretation, and our own hypothesis. A fan comment is one person's perspective, not a survey.
- Never claim to have heard audio, watched a performance, read lyrics, or used software without actually doing so. Name the evidence available. Browser text or video metadata is not listening.
- Where audio is available to the agent, record the version and timestamps for specific observations. Where it is not, advance source research and keep listening questions open.
- Seek contrasting eras, genres, languages, and scales of audience. Do not turn fandom into a popularity ranking or an arbitrary completion count.
- Summarize themes in original prose. Link to lyrics rather than copying or translating entire songs.

## Public repository

- Never print or commit passwords, access tokens, cookies, pairing codes, private correspondence, personal machine paths, or sensitive configuration.
- Do not commit third-party recordings, artwork, lyrics, samples, installers, or voicebanks without appropriate rights. Keep locally licensed assets in ignored directories or outside the repository.
- Review the exact staged diff, check local Markdown links, and run `git diff --check` before committing. Add meaningful behavioral checks when actual code is introduced.
- Stage only the intended files. Do not force-push, rewrite others' history, or discard user changes. Verify the remote result after publishing.
- Contributions and public links are welcome. Do not contact people, post comments, or send messages on the owner's behalf without explicit authorization. Permission to push repository work is not permission for outreach.

## Learning and creative work

Song listening, reviewing, and learning are the current priority. Follow only the next song-learning direction explicitly reviewed and dispatched by the parent assistant. The parent may choose learning directions and preserve optional ideas within this scope; parent review alone cannot authorize new instrumental or Vocaloid production. Spontaneous creative ideas may be recorded as optional possibilities; they do not require a sketch, MIDI export, instrumental generation, or Vocaloid production. Preserve existing creative work without making its unfinished experiments obligations. Production remains deferred until the owner explicitly authorizes new production; roadmap dates and software requests do not open that gate.

In a session note, preserve what drew interest, what remains puzzling, why an interpretation changed, and the evidence actually available. Use relevant source/version links and timestamps where assessed, distinguishing direct listening, attributed owner feedback, machine estimates, and text-only research. Revisit questions when useful; there is no quota or mandatory full checklist, and learning need not yield a songwriting technique.

## Parent review

Parent review of actual outputs and the next direction is required. If that review is unavailable, preserve the verified state and wait; do not independently select or resume a task. Additional ChatGPT consultation is optional within a dispatched task and does not replace parent review. Use only a connection verified to point at beMiku, keep private connection state outside the repository, and do not treat a model's response as a research source. The parent updates the owner directly; daily parent review replaces the paused self-directed schedule, which must not be resumed.
