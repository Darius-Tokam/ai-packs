---
name: recycle-my-post
description: Run the full post-recycler procedure when the user asks, in any language, to repurpose, recycle or adapt one post for other networks or formats ("recycle ce post en plusieurs formats", "décline mon post LinkedIn pour X et Instagram", "transforme ce post en carrousel et en fil", "repurpose this post for X and Instagram", "turn this LinkedIn post into a thread and a newsletter"). Same procedure as /post-recycler:recycle, started by the request instead of the command.
---

# recycle-my-post

The user asked to repurpose a post. Run the same procedure as `/post-recycler:recycle`, started by the request instead of the command.

## 1. Source

- The source is the post the user pasted or the file they named. If neither is clear, ask once for it. Save it as `recycled/source.md` exactly as given.
- Take the link to promote and the target language from the request when they are there (same language as the source by default). Ask once for what is missing, never for what the request already says.
- If the user named only some formats ("pour X et Instagram"), write those first, then offer the other formats in one line.

## 2. The formats, in this order

One file each in `recycled/`:

1. `x-writer`: `x-post.md`, `x-thread.md`
2. `short-posts`: `threads.md`, `bluesky.md`
3. `carousel`: `carousel.md`
4. `insta-caption`: `instagram.md`
5. `video-script`: `video-script.md`
6. `newsletter`: `newsletter.md`
7. `quote-card`: `quote-card.md`, `story.md`

## 3. The guard

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_formats.py" --source recycled/source.md --dir recycled/ [--allow <link>]
```

Rewrite each failing format and rerun until every written format passes. Say how many rounds it took. Print the guard table, then each format in a code block.

Never add a fact, a number, a client or a link that is not in the source. Never post anything: the creator copies and posts.
