---
description: Recycle one post into 10 formats (X post and thread, Threads, Bluesky, carousel, Instagram, 30 s video, newsletter, quote card, story), checked by script.
argument-hint: "[path to the post, or paste it after the command]"
---

Recycle this post into 10 formats: $ARGUMENTS

1. Save the source as `recycled/source.md` exactly as given (if it is a path, copy the file). Ask once for the link to promote, if any, and the target language (same as the source by default).
2. Write the formats with these skills, one file each in `recycled/`:
   1. `x-writer`: `x-post.md`, `x-thread.md`
   2. `short-posts`: `threads.md`, `bluesky.md`
   3. `carousel`: `carousel.md`
   4. `insta-caption`: `instagram.md`
   5. `video-script`: `video-script.md`
   6. `newsletter`: `newsletter.md`
   7. `quote-card`: `quote-card.md`, `story.md`
3. Run `fact-guard`:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_formats.py" --source recycled/source.md --dir recycled/ [--allow <link>]
   ```
   Rewrite each failing format and rerun until 10/10 PASS. Say how many rounds it took.
4. Print the guard table, then each format in a code block, in the order above.

Never add a fact, a number, a client or a link that is not in the source. Never post anything: the creator copies and posts.
