#!/usr/bin/env python3
"""Repair the activity-description return lines in zep_graph_memory_updater.py."""
import re

P = "backend/app/services/zep_graph_memory_updater.py"
lines = open(P, encoding="utf-8").read().splitlines(keepends=True)

out = []
for l in lines:
    s = l.rstrip("\n")
    indent = s[: len(s) - len(s.lstrip())]
    t = s.strip()
    new = None
    if t.startswith("return f'") or t.startswith('return f"'):
        # Normalize every description return line to a double-quoted f-string
        # with escaped inner double quotes, rebuilt from a known-good table.
        if "posted" in t and "{content}" in t:
            new = indent + 'return f"posted: \\"{content}\\""'
        elif t == 'return "made a post"' or t == "return f'made a post'":
            new = indent + 'return "made a post"'
        elif "liked" in t and "post_author" in t and "post_content" in t:
            new = indent + 'return f"liked {post_author}\'s post: \\"{post_content}\\""'
        elif "liked" in t and "post_content" in t:
            new = indent + 'return f"liked a post: \\"{post_content}\\""'
        elif "liked" in t and "post_author" in t:
            new = indent + 'return f"liked a post by {post_author}"'
        elif t.startswith('return "liked a post"'):
            new = indent + 'return "liked a post"'
        elif "disliked" in t and "post_author" in t and "post_content" in t:
            new = indent + 'return f"disliked {post_author}\'s post: \\"{post_content}\\""'
        elif "disliked" in t and "post_content" in t:
            new = indent + 'return f"disliked a post: \\"{post_content}\\""'
        elif "disliked" in t and "post_author" in t:
            new = indent + 'return f"disliked a post by {post_author}"'
        elif t.startswith('return "disliked a post"'):
            new = indent + 'return "disliked a post"'
        elif "reposted" in t and "original_author" in t and "original_content" in t:
            new = indent + 'return f"reposted {original_author}\'s post: \\"{original_content}\\""'
        elif "reposted" in t and "original_content" in t:
            new = indent + 'return f"reposted a post: \\"{original_content}\\""'
        elif "reposted" in t and "original_author" in t:
            new = indent + 'return f"reposted a post by {original_author}"'
        elif t.startswith('return "reposted a post"'):
            new = indent + 'return "reposted a post"'
        elif "quoted" in t and "original_author" in t and "original_content" in t:
            new = indent + 'return f"quoted {original_author}\'s post \\"{original_content}\\""'
        elif "quoted" in t and "original_content" in t:
            new = indent + 'return f"quoted a post \\"{original_content}\\""'
        elif "quoted" in t and "original_author" in t:
            new = indent + 'return f"quoted a post by {original_author}"'
        elif t.startswith('return "quoted a post"'):
            new = indent + 'return "quoted a post"'
        elif "commented" in t and "quote_content" in t:
            new = indent + 'base += f\' and commented: "{quote_content}"\''
        elif "followed user" in t and "target_user_name" in t:
            new = indent + 'return f"followed user \\"{target_user_name}\\""'
        elif t.startswith('return "followed a user"'):
            new = indent + 'return "followed a user"'
        elif "commented on" in t and "post_author" in t and "post_content" in t and "content" in t:
            new = indent + 'return f"commented on {post_author}\'s post \\"{post_content}\\": \\"{content}\\""'
        elif "commented on" in t and "post_content" in t and "content" in t:
            new = indent + 'return f"commented on the post \\"{post_content}\\": \\"{content}\\""'
        elif "commented on" in t and "post_author" in t and "content" in t:
            new = indent + 'return f"commented on {post_author}\'s post: \\"{content}\\""'
        elif "commented:" in t and "content" in t:
            new = indent + 'return f\'commented: "{content}"\''
        elif t.startswith('return "left a comment"'):
            new = indent + 'return "left a comment"'
        elif "liked" in t and "comment_author" in t and "comment_content" in t:
            new = indent + 'return f"liked {comment_author}\'s comment: \\"{comment_content}\\""'
        elif "liked" in t and "comment_content" in t:
            new = indent + 'return f"liked a comment: \\"{comment_content}\\""'
        elif "liked" in t and "comment_author" in t:
            new = indent + 'return f"liked a comment by {comment_author}"'
        elif t.startswith('return "liked a comment"'):
            new = indent + 'return "liked a comment"'
        elif "disliked" in t and "comment_author" in t and "comment_content" in t:
            new = indent + 'return f"disliked {comment_author}\'s comment: \\"{comment_content}\\""'
        elif "disliked" in t and "comment_content" in t:
            new = indent + 'return f"disliked a comment: \\"{comment_content}\\""'
        elif "disliked" in t and "comment_author" in t:
            new = indent + 'return f"disliked a comment by {comment_author}"'
        elif t.startswith('return "disliked a comment"'):
            new = indent + 'return "disliked a comment"'
        elif "searched for" in t and "{query}" in t and "users" not in t:
            new = indent + 'return f\'searched for "{query}"\' if query else "performed a search"'
        elif "searched for users" in t and "{query}" in t:
            new = indent + 'return f\'searched for users "{query}"\' if query else "searched for users"'
        elif "muted user" in t and "target_user_name" in t:
            new = indent + 'return f"muted user \\"{target_user_name}\\""'
        elif t.startswith('return "muted a user"'):
            new = indent + 'return "muted a user"'
        elif "performed a {self.action_type}" in t:
            new = indent + 'return f"performed a {self.action_type} action"'
    out.append((new + "\n") if new is not None else l)

open(P, "w", encoding="utf-8").write("".join(out))
print("normalized")
