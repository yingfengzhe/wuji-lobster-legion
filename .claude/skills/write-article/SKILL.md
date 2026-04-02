# Write Article - AI-Powered Content Creation with Humanization

**Trigger:** "write article", "write an article about", "create content for"

## What This Does

Writes complete, SEO-optimized, human-sounding articles:
1. **Researches topic** - Analyzes top-ranking content
2. **Creates comprehensive outline** - Better than competitors
3. **Writes 1500-2500 words** - Long-form, detailed content
4. **Humanizes** - Removes AI patterns (MANDATORY)
5. **Optimizes for SEO** - Target keywords, meta tags, structure
6. **Outputs markdown** - Ready to publish

## Process

### Phase 1: Research
1. **Identify target keyword** from article topic
2. **Search for keyword** - Find top 5 ranking pages
3. **Analyze competitors:**
   - What topics do they cover?
   - How comprehensive are they?
   - What's their word count?
   - What's missing or weak?
   - What unique angles can we take?
4. **Gather additional context** - Related questions, subtopics

### Phase 2: Outline Creation
Build outline that beats competitors:
- **H2 sections:** 5-7 main sections
- **H3 subsections:** 2-4 per H2
- **Include:**
  - Introduction with hook
  - Main content sections
  - FAQ section (for featured snippets)
  - Conclusion with CTA
- **Plan:** Where to naturally include target keywords

### Phase 3: Writing (First Draft)
Write comprehensive, engaging content:
- **Intro:** Hook + promise + context (150-200 words)
- **Body sections:** Detailed, scannable, practical (1200-1800 words)
  - Use bullet points, numbered lists
  - Include specific examples
  - Add practical tips
  - Reference real places/experiences when relevant
- **FAQ:** 5-7 common questions with direct answers
- **Conclusion:** Summarize + CTA (150-200 words)

**Writing guidelines:**
- Conversational but authoritative tone
- Short paragraphs (2-4 sentences)
- Varied sentence length
- Active voice preferred
- Real details, not generic fluff
- Second person ("you") for connection

### Phase 4: Humanization (MANDATORY)
**This is what makes the difference.**

Run the draft through humanizer skill to remove:
- ✗ Inflated symbolism ("tapestry of", "symphony of")
- ✗ Promotional language ("unparalleled", "world-class")
- ✗ Superficial -ing phrases ("offering", "providing", "ensuring")
- ✗ Vague attributions ("experts say", "research shows" without specifics)
- ✗ Em dash overuse
- ✗ Rule of three everywhere
- ✗ AI vocabulary (delve, meticulous, meticulously, realm, etc.)
- ✗ Excessive conjunctive adverbs

Replace with:
- ✓ Specific details and examples
- ✓ Direct, clear language
- ✓ Varied sentence structures
- ✓ Concrete claims with context
- ✓ Natural transitions

**Never skip this step.** This is what separates AI content from human-quality content.

### Phase 5: SEO Optimization
Add final SEO elements:
- **Title tag** (50-60 chars, keyword-optimized)
- **Meta description** (150-160 chars, compelling CTA)
- **Keyword placement:**
  - Title/H1
  - First paragraph
  - 2-3 H2 headings
  - Throughout body (natural density)
  - Conclusion
- **Internal link suggestions** (3-5 related articles)
- **Image alt text examples** (5-7 images needed)
- **Schema markup recommendation**

### Phase 6: Output
Save as markdown with frontmatter:
```markdown
---
title: "SEO-optimized title"
meta_description: "Compelling meta description"
target_keyword: "primary keyword"
word_count: XXXX
created: YYYY-MM-DD
status: ready
---

[Article content]

---

## Internal Linking Opportunities
- Link to: [Related article 1]
- Link to: [Related article 2]

## Images Needed
1. [Image description] - Alt: "keyword-rich alt text"
2. [Image description] - Alt: "keyword-rich alt text"

## Schema Markup
Recommend: [Article / FAQ / HowTo schema]
```

## Content Types & Templates

### SEO Blog Post (Informational)
**Use for:** "best X", "guide to X", "how to X"
**Structure:**
- Intro (hook + promise)
- 5-7 H2 sections
- FAQ section
- Conclusion + CTA
**Example:** "10 Best Bangkok Hostels for Solo Travelers 2026"

### Location Page (Programmatic SEO)
**Use for:** City/neighborhood keywords
**Structure:**
- Overview of area
- Best hostels in area (3-5 highlighted)
- What to do in area
- Transportation/practical info
- FAQ
**Example:** "Best Hostels in Sukhumvit, Bangkok"

### Comparison Article
**Use for:** "X vs Y", "which is better"
**Structure:**
- Intro: What we're comparing
- Side-by-side comparison table
- Detailed breakdown per option
- Verdict/recommendation
- FAQ
**Example:** "Khao San Road vs Sukhumvit: Where to Stay in Bangkok"

### Ultimate Guide (Pillar Content)
**Use for:** Broad topics, hub pages
**Structure:**
- Comprehensive intro
- Table of contents
- 7-10 major sections
- Multiple FAQs
- Resource links
**Example:** "The Complete Guide to Bangkok Hostels (2026)"

### How-To Guide
**Use for:** Process/instruction keywords
**Structure:**
- Why this matters
- What you need
- Step-by-step instructions
- Tips & warnings
- FAQ
**Example:** "How to Choose a Bangkok Hostel (First-Timer's Guide)"

## Special Handling for Trevor's Hostels

When writing hostel/Thailand content, include:

**Hostel context:**
- Dorm vs private room options
- Social atmosphere indicators
- Common spaces (rooftop, lounge, kitchen)
- Booking considerations

**Thailand context:**
- Visa information (where relevant)
- Transport options (BTS, MRT, taxi, tuk-tuk)
- Cultural considerations
- Safety tips (especially for solo travelers)
- Seasonal factors (rainy season, high season)
- Budget ranges in Thai Baht + USD

**Local details:**
- Specific neighborhoods
- Nearby attractions
- Walking distances
- Street names/landmarks
- Local food/markets

**Trust signals:**
- "Based on 200+ hostel reviews"
- "Verified by backpackers who stayed there"
- "Updated for 2026"
- Specific booking platforms mentioned

## Integration

This skill:
- **Uses** marketing-skills/references/copywriting/ for writing best practices
- **Uses** humanizer skill (mandatory post-processing)
- **References** seo-audit for optimization checks
- **Can pull from** content-strategy output (write articles from the plan)
- **Outputs to** `/seo-employee/output/articles/`

## Quality Checklist

Before saving, verify:
- [ ] 1500-2500 words minimum
- [ ] Target keyword in title, H1, first paragraph
- [ ] 5-7 H2 sections with logical flow
- [ ] Bullet points/lists for scannability
- [ ] Specific examples, not generic statements
- [ ] **HUMANIZED** (no AI patterns)
- [ ] FAQ section (3-7 questions)
- [ ] Strong introduction (hook + promise)
- [ ] Clear conclusion with CTA
- [ ] Meta title (50-60 chars)
- [ ] Meta description (150-160 chars)
- [ ] Internal link suggestions
- [ ] Image descriptions + alt text

## Example Usage

```
Write an article about "Best Budget Hostels in Bangkok 2026"
```

```
Create content for: Bangkok hostels with swimming pools
```

```
Write article: How to Choose a Hostel in Chiang Mai
```

```
Generate article from this topic: [paste from content-strategy output]
```

## Output Example

Article saved to: `/seo-employee/output/articles/best-budget-hostels-bangkok-2026.md`

Includes:
- Full markdown article (1500-2500 words)
- SEO metadata (title, description, keywords)
- Humanized content (AI patterns removed)
- Internal linking suggestions
- Image recommendations
- Ready to publish

---

**This is the core content creation engine.** Every article goes through:
Research → Outline → Write → Humanize → Optimize → Output

**The humanization step is what makes this valuable.** Anyone can generate AI content. We're creating human-quality content at scale.

---

**Status:** Ready to use. Can write standalone or as part of /full-pipeline.

**Pro tip:** Review the humanizer skill (`/home/desktop/clawd/skills/humanizer/SKILL.md`) to understand what patterns it removes. This is the secret sauce.
