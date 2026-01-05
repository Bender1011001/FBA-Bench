# Multi-Touch Outbound Email Sequence Template

## Overview and Personalization Guidance

This template provides a 5-email sequence for enterprise outreach targeting Ideal Customer Profiles (ICPs) in sectors like SaaS, FinTech, Healthcare, and more. The sequence builds awareness of FBA-Bench Enterprise's value in standardizing AI model evaluations, addressing pain points, and driving meetings.

**How to Use:**
- Import the ICP CSV from `../targets/top20_icp.csv` into a mail merge tool (e.g., HubSpot, Outreach.io, or Google Sheets with add-ons).
- Replace merge tags (e.g., {{COMPANY}}) with data from CSV columns.
- Personalize further: Research the contact's recent posts or company news to add 1-2 specific details (e.g., "Saw your team's recent scaling challenges at [Event]").
- Cadence: Send on specified days; pause on reply or opt-out.
- Length: Keep under 150 words per email for high engagement.
- Testing: A/B test subject lines; track opens/replies.
- Opt-out: Include in every email; honor immediately.

**Line-by-Line Personalization Instructions:**
- Use CSV data for core tags (e.g., {{COMPANY}} from "company" column).
- Tailor {{PAIN_POINT}} and {{ROI}} based on "key_pain_points" and company context.
- Insert {{MEETING_LINK}} as a Calendly/Zoom placeholder (e.g., https://example.com/demo?{{COMPANY}}).
- Add sender signature at the end (name, role, contact, company).

## Merge Tags Legend

- {{FIRST_NAME}}: Contact's first name (e.g., John from "contact_name").
- {{LAST_NAME}}: Contact's last name (e.g., Doe).
- {{COMPANY}}: Company name (e.g., Acme Analytics from "company").
- {{ROLE}}: Job title (e.g., CTO from "contact_title").
- {{PAIN_POINT}}: Key challenge (e.g., "Inconsistent AI model evaluations" from "key_pain_points").
- {{RESULT}}: Expected outcome (e.g., "standardized evals across teams").
- {{ROI}}: Benefit quantification (e.g., "40% faster iterations and compliance assurance").
- {{CALL_TO_ACTION}}: CTA phrase (e.g., "Book a 15-min demo").
- {{MEETING_LINK}}: Scheduling link (e.g., https://example.com/meeting?{{COMPANY}}).

## Day 0: Initial Outreach

**Subject:** {{FIRST_NAME}}, streamlining {{PAIN_POINT}} at {{COMPANY}}?

**Body:**
Hi {{FIRST_NAME}} {{LAST_NAME}},

As {{ROLE}} at {{COMPANY}}, you're tackling {{PAIN_POINT}} head-on. Many enterprise teams face similar hurdles with fragmented tools, leading to delays and risks.

FBA-Bench Enterprise delivers {{RESULT}} through automated, compliant benchmarking—seamlessly integrating with your tech stack for reliable insights.

Teams like yours achieve {{ROI}}. {{CALL_TO_ACTION}} to see it in action?

[Schedule here: {{MEETING_LINK}}]

If now’s not a fit, reply ‘stop’ and I’ll close the loop.

Best,  
[Your Name]  
[Your Role], FBA-Bench Enterprise  
[Your Email] | [Your LinkedIn]

## Day 3: Value Follow-Up

**Subject:** Quick win for {{COMPANY}}'s {{PAIN_POINT}}, {{FIRST_NAME}}?

**Body:**
Hi {{FIRST_NAME}},

Following up—thought this might help with {{PAIN_POINT}} at {{COMPANY}}. Our guide on enterprise AI evals highlights common pitfalls and how to {{RESULT}}.

Download: https://example.com/ai-evals-guide

With FBA-Bench, unlock {{ROI}} without overhauling your stack. Worth 10 minutes to discuss?

[Book time: {{MEETING_LINK}}]

Reply ‘stop’ if uninterested.

Regards,  
[Your Name]  
[Your Role], FBA-Bench Enterprise  
[Your Email] | [Your LinkedIn]

## Day 7: Case Study/ROI Angle

**Subject:** How peers achieved {{ROI}} amid {{PAIN_POINT}}

**Body:**
Hello {{FIRST_NAME}},

A similar {{ROLE}} at a FinTech firm (like {{COMPANY}}) used FBA-Bench to overcome {{PAIN_POINT}}, delivering {{RESULT}} and {{ROI}}—cutting eval time by 50% while ensuring compliance.

Case study attached: https://example.com/case-study-fintech

Let's tailor this for {{COMPANY}}. {{CALL_TO_ACTION}}?

[Meet: {{MEETING_LINK}}]

Opt out: reply ‘stop’.

Cheers,  
[Your Name]  
[Your Role], FBA-Bench Enterprise  
[Your Email] | [Your LinkedIn]

## Day 10: Bump (Short)

**Subject:** Still relevant for {{COMPANY}}? {{PAIN_POINT}} solution

**Body:**
{{FIRST_NAME}},

Quick bump: FBA-Bench can help {{COMPANY}} achieve {{RESULT}} and {{ROI}} on {{PAIN_POINT}}.

15-min chat? [{{MEETING_LINK}}]

Reply ‘stop’ to pause.

Best,  
[Your Name]  
[Your Role], FBA-Bench Enterprise

## Day 14: Breakup (Polite Close)

**Subject:** Closing the loop on {{COMPANY}} outreach, {{FIRST_NAME}}

**Body:**
Hi {{FIRST_NAME}},

Over two weeks, I've shared how FBA-Bench addresses {{PAIN_POINT}} with {{RESULT}} and {{ROI}} for teams like {{COMPANY}}'s.

If this isn't timely, I'll step back—no hard feelings. Reply if priorities shift.

Final {{CALL_TO_ACTION}}: [{{MEETING_LINK}}]

Reply ‘stop’ to unsubscribe fully.

Thanks,  
[Your Name]  
[Your Role], FBA-Bench Enterprise  
[Your Email] | [Your LinkedIn]
