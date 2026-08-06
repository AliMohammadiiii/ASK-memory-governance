# Sanitized corrected engineering package

This package excludes raw StudyChat/WikiConv source bytes, `.private/`, HMAC
secrets, source mappings, individual AI-provisional annotation rows, private
split manifests, and human-review queues. Place raw inputs in an external
private directory and set `MGP_FULL_INPUTS` as described in `README_FIRST.md`.

