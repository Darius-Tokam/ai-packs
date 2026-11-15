---
name: short-posts
description: Rewrite a long post for Threads (500 UTF-8 bytes) and Bluesky (300 characters), each with its own opening line. Use when recycling a post for Threads or Bluesky.
---

# short-posts

## threads.md

- 500 bytes at most: Threads counts UTF-8 bytes, so every accented letter (é, à, ç) counts double. A French post of 450 characters can be over the limit. The guard measures bytes.
- Conversational: first person, one result, one detail that makes it concrete, one line that invites a reply (a choice between two options works better than "what do you think?").

## bluesky.md

- 300 characters at most.
- Start with a different line than threads.md and x-post.md: Bluesky readers often follow the same people on X.
- One result, one proof, the link if there is one.

## Rules

Only facts and numbers from the source. No hashtag, no long or medium dash. Run `fact-guard` after writing.
