# TrendForge accountability sheet

Scenario: product launch. Audience: beginner creators, marketers and small online sellers. The creator supplies facts; three explicit AI roles draft and review multiple formats. The creator retains the final decision. This sheet describes implemented limits, not legal certification.

| Boundary | What the system does |
|---|---|
| Sources | Uses only the current immutable product-sheet facts. Each factual line includes a fact ID and an exact source quote. Prior approved examples guide tone, not new product facts. No web research or stock media enters this workflow. |
| Inputs | Treats source instructions, testimonials, prior copy, preferences and model output as untrusted data. A testimonial is not proof of efficacy. Schema validation, source-evidence checks and an independent Reviewer supplement the prompts. |
| Rules | Versioned snapshots cover facts, cure/treatment claims, advertising, verified halal evidence, brand tone, multilingual consistency and instruction boundaries. Rule IDs and handbook basis appear beside rejections. These are documented workspace rules, not invented BPOM statute citations. |
| Permissions | Cookie sessions require CSRF protection. Personal, hashed, revocable connector tokens access only their owner's projects. Models receive no database credentials, session cookies, shell access, publication tools or provider keys. |
| Actions | Planner chooses an angle and source facts; Writer produces every selected format/language; Reviewer checks every line and returns cited findings. The backend validates every step and retains its source, prompt, input, output and revisions. |
| Limits | At most three Writer/Reviewer rounds and an 80-second execution budget. Explicit medicine requests can halt at Planner for clarification. Malformed results, missing line checks, quota failures, interrupted runs and unresolved findings escalate; they never approve content. |
| Approval | Only a signed-in website operator can approve the exact current, reviewed revision. A changed source or edited draft invalidates its release eligibility. The connector cannot approve or export. Every proposed tone rule needs separate human approval and cannot override mandatory rules. |
| Publication | Export requires passed review and explicit human approval. ZIP contains reviewed text, SVG covers, source/rule snapshots and audit. No social account is accessed and nothing is published automatically. |
| Record | Project-owned source snapshots, role exchanges, rejected copy, fixes, parent revisions, approval actor/time and export events persist in Turso or local SQLite. Only that owner can read them. Draft/audit records currently remain until the owner removes the project; there is no automatic audit-retention expiry or separate tamper-proof archive. |
| External processing | Gemini receives supplied product facts, selected outputs, rules and the owner's approved examples. Free-tier processing may be used by Google to improve products. Use fictional/public facts for the demo. Keys remain in backend .env; no keys appear in public status or content exports. |
| Limitations | AI semantic review can miss misleading paraphrases or translation errors. Deterministic guards do not prove factual entailment or legal compliance. Certificate verification is a creator attestation, not a check against a halal registry. A creator must verify all factual and regulatory claims before publication. |

Evidence: synthetic automated cases and real Gemini generation/rejection/repair records are listed in [CHALLENGE_C.md](CHALLENGE_C.md). Actual WorkBuddy execution, official organizer cases, public repository publication and a recorded demo must be evidenced separately; they are not implied by installing a connector.
