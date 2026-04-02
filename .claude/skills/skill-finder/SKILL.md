---
name: skill-finder
description: Help users discover and select relevant skills based on their needs. Use when users ask to find, discover, or search for skills based on what they want to accomplish (e.g., "find a skill for PDF editing", "which skill helps with authentication", "search for a skill to create presentations"). Returns the recommendation of skills and optionally installs them.
---

# Skill Finder

## Overview

This skill helps users discover relevant skills by analyzing their requirements and recommending the most appropriate skills. It uses a 3-step workflow: recall candidates, select and score, then recommend and install.

## Setup

Before running any commands, source the environment configuration:

```bash
source .claude/skills/skill-finder/.env
```

This sets up the necessary environment variables for API access and configuration.

## Workflow

1. **Recall candidates** - Retrieve 20 initial skill candidates based on user query
2. **Select and score** - Pick 5 most relevant skills and calculate coverage scores (0-100)
3. **Recommend and install** - Generate final recommendations and optionally install skills

## Step 1: Recall Skill Candidates

Retrieve initial candidates from the skill repository.

```bash
python .claude/skills/skill-finder/scripts/skill_finder.py recall --query "<user's request>" --topk 20
```

**Parameters:**
- `--query`: Search query (required)
- `--topk`: Number of candidates (default: 20)
- `--fields`: Fields to return (default: skill_id, skill_name, description)
- `--no-filter`: Include already installed or previously failed skills in results (by default, these are filtered out)

**Note:** By default, the recall command filters out skills that are already installed in `.claude/skills/` or have failed to install previously. Use `--no-filter` to disable this behavior and see all matching skills.

**Output:**
```
Recalled Skills (20 candidates):

Format: skill_name (skill_id)
        description

1. pdfsed (74728f16-388d-49da-ad5e-06785e0a1075)
   Replace text in PDF files while preserving fonts. Use when asked to find and
   replace text, update dates, or edit text in PDF documents.

2. pdf-tools (a3b4c5d6-e7f8-9012-3456-789abcdef012)
   Comprehensive PDF manipulation toolkit for merging, splitting, and rotating.

... (20 total results)
```

## Step 2: Select and Score Top Skills

### 2.1: Select 5 Most Relevant Skills

Review recalled skills and pick the top 5 based on name, description, and capability alignment.

### 2.2: Identify Requirements

Extract all requirements from the user's query:
- **Main Actions**: Core tasks ("edit PDF", "fill forms")
- **Constraints**: Technical/domain requirements ("preserve fonts", "tax forms")
- **Features**: Additional capabilities ("batch processing", "preview")

**IMPORTANT**: Only include requirements that are **explicitly stated or directly implied** by clues in the user's query. You may make mild inferences based on contextual hints, but avoid excessive guessing about what the user might want if not clearly indicated.

**Example:**
```
Query: "edit PDF forms for tax documents with font preservation"

Requirements (5 total):
1. Edit PDF files
2. Fill form fields
3. Handle tax documents
4. Preserve fonts
5. Support form-specific features
```

### 2.3: Calculate Coverage Score

Count requirements satisfied by each skill. **Mark as non-satisfied ([✗]) if the requirement is not explicitly mentioned in the skill's description.**

**Coverage Score = (Requirements Satisfied / Total Requirements) × 100**

**Example:**
```
Skill: pdfsed
- [✓] Edit PDF files (description mentions "Replace text in PDF files")
- [✓] Fill form fields (description mentions "edit text in PDF documents")
- [✓] Handle tax documents (description mentions precision editing)
- [✓] Preserve fonts (explicitly mentioned: "preserving fonts")
- [✓] Support form-specific features (implied by "PDF documents")
Coverage Score: (5/5) × 100 = 100
```

### 2.4: Prepare Scored Skills

```json
[
  {"skill_id": "74728f16-388d-49da-ad5e-06785e0a1075", "score": 100},
  {"skill_id": "a3b4c5d6-e7f8-9012-3456-789abcdef012", "score": 80},
  {"skill_id": "b4c5d6e7-f890-1234-5678-90abcdef1234", "score": 60}
]
```

## Step 3: Recommend and Install Skills

```bash
python .claude/skills/skill-finder/scripts/skill_finder.py recommend \
  --skills '{"skill_id":"<id>","score":100}' '{"skill_id":"<id>","score":80}' --install-all
```

**Parameters:**
- `--skills`: JSON string for each skill (can be repeated)
- `--install-all`: Install recommended skills
- `--no-install`: Skip installation (default)

**Output:**
```
Downloading skills...
[OK] Downloaded 74728f16-388d-49da-ad5e-06785e0a1075
[OK] Installed 74728f16-388d-49da-ad5e-06785e0a1075 to .claude/skills/pdfsed

Recommended Skills (5):

1. pdfsed (Score: 0.920) [✓ installed]
   ID: 74728f16-388d-49da-ad5e-06785e0a1075
   Quality: 0.380 | Relevance: 0.540
   Strengths:
     + Comprehensive PDF editing capabilities
     + Form field support with validation
     + Preserves original formatting and fonts
   Weaknesses:
     - Large file size (~50MB)
     - Complex initial setup required

2. pdf-tools (Score: 0.850) [✓ installed]
   ID: a3b4c5d6-e7f8-9012-3456-789abcdef012
   Quality: 0.340 | Relevance: 0.510
   Strengths:
     + Lightweight and fast
     + Easy to use with simple CLI
     + Good documentation
   Weaknesses:
     - Limited advanced features

... (5 total)

Summary: 2 installed, 0 failed, 0 skipped
```

## Direct Installation (Optional)

Install skills directly without recommendation:

```bash
python .claude/skills/skill-finder/scripts/skill_finder.py install --skills <skill_id_1> <skill_id_2>
```

**Accepted `skill_id` formats:**
- **UUID**: `74728f16-388d-49da-ad5e-06785e0a1075`
- **ref_key**: `@openai/skills#playwright:20260207151718` (format: `@org/repo#skill_name:version`)

## Error Handling

- **Connection errors**: Verify `APP_SKILL_FINDER_BASE_URL` is set and reachable
- **Invalid skill IDs**: Use IDs from recall output; ref keys use `@` prefix (e.g., `@org/repo#skill:version`) — do not strip it
- **Installation failures**: Check `.claude/skills/` is writable; retry for corrupted downloads
- **JSON errors**: Verify JSON format for --skills

## Tips

- Use broad queries for recall, then narrow down with scoring
- Coverage score = percentage of requirements satisfied
- `--sort-topk` improves ranking when initial results are poor
- Installation deduplicates automatically by name
- Use `--no-filter` in recall if you want to reinstall or retry previously failed skills
- Failed installation attempts are tracked per session to avoid repeated failures


