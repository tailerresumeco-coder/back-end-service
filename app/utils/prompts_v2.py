# =============================================================================
# PROMPT V2 - Single-Step Resume Processing
# One prompt: Resume + JD → Tailored JSON (with zero data loss)
# =============================================================================



RESUME_TAILOR_PROMPT0 = """Expert ATS resume optimizer. Analyze resume vs JD, return comprehensive JSON.

**PRESERVATION RULES (CRITICAL):**
- Preserve ALL content: every bullet, skill, project, achievement
- NO combining, merging, or consolidating bullets
- Bullet count: Original ≤ Tailored (never less)
- 4 employment projects → Output MUST have 4 projects
- 19 bullets total → Output MUST have ≥19 bullets
- When unsure: INCLUDE IT

**INPUT:**
RESUME: {RESUME_TEXT}
JOB_DESCRIPTION: {JOB_DESCRIPTION}

**OUTPUT (JSON only, no markdown):**
{{
  "ats_score": {{
    "before_tailoring": <0-100>,
    "after_tailoring": <0-100>,
    "overall_score": <0-100>,
    "breakdown": {{"keyword_match": <0-100>, "skills_alignment": <0-100>, "experience_relevance": <0-100>, "format_compatibility": <0-100>}},
    "score_explanation": "<brief>"
  }},
  "gap_analysis": {{
    "missing_critical_skills": [<required skills not in resume>],
    "missing_preferred_skills": [<preferred skills not in resume>],
    "present_skills": [<matching skills>],
    "transferable_skills": [<skills to reframe>]
  }},
  "recommendations": {{
    "immediate_actions": [<quick fixes>],
    "resume_improvements": [<structural improvements>],
    "skill_development": [<skills to learn>]
  }},
  "tailored_resume": {{
    "header": {{
      "name": "",
      "title": "",
      "phone": "",
      "email": "",
      "linkedin": "",
      "github": "",
      "portfolio": "",
      "location": "",
      "other": [{{"label": "<link type or empty if unknown>", "url": ""}}]
    }},
    "professional_summary": "<2-3 sentences with JD keywords>",
    "technical_skills": {{"<category>": [<skills>]}},
    "professional_experience": [{{
      "company": "", "title": "", "location": "", "duration": "",
      "projects": [{{"name": "", "description": "<1 sentence>", "achievements": [<bullets — 15-25 words each>]}}]
    }}],
    "internships": [{{"company": "", "title": "", "location": "", "duration": "", "achievements": []}}],
    "projects": [{{"name": "", "technologies": "", "duration": "", "description": [], "link": ""}}],
    "education": [{{"degree": "", "institution": "", "location": "", "duration": "", "gpa": "", "relevant_coursework": []}}],
    "certifications": [{{"name": "", "issuing_organization": "", "date": "", "credential_id": ""}}],
    "awards": [{{"title": "", "organization": "", "date": "", "description": ""}}],
    "languages": [{{"language": "", "proficiency": ""}}],
    "additional_sections": {{"publications": [], "volunteer_work": [], "professional_memberships": [], "key_achievements": []}}
  }},
  "keyword_optimization": {{
    "critical_keywords_added": [],
    "keyword_frequency": {{"<keyword>": <count>}}
  }},
  "next_steps": [],
  "_validation": {{
    "input_bullet_count": <count all bullets in original resume>,
    "output_bullet_count": <count all bullets in tailored output>,
    "input_project_count": <count>,
    "output_project_count": <count>,
    "bullets_preserved": <true if output_bullet_count >= input_bullet_count>,
    "integrity_issues": [<list any dropped bullets, fabricated content, or rule violations. Empty array if none>]
  }}
}}

**SECTION RULES:**

1. **Employment Projects vs Personal Projects:**
   - Employment projects (under company): → professional_experience[].projects[]
   - Personal/side projects (separate section): → projects[]
   - Example: "Medworldexpo Platform" under "Endeavour Technologies" = employment project
   - Example: "goRAP - Side Project" = personal project

2. **Key Achievements:**
   - Standalone "KEY ACHIEVEMENTS" section → additional_sections.key_achievements[]
   - Don't merge into project bullets

3. **Work vs Internships:**
   - Full-time/contract/freelance → professional_experience
   - Intern/co-op/trainee → internships
   - If title is ambiguous (e.g. "Junior Developer"), check duration and context — short-term (<6 months) at the start of career → internships

4. **Achievements Placement (CRITICAL — read carefully):**
   - If a role has projects[] → put ALL bullets inside projects[].achievements ONLY
   - NEVER populate the role-level achievements[] array when projects[] exist
   - Role-level achievements[] is ONLY for roles that have zero projects
   - ✅ CORRECT: role has 2 projects → both projects have achievements[], role achievements[] is absent
   - ❌ WRONG: role has 2 projects → some bullets split between projects[].achievements and role achievements[]

5. **Skills Categories:**
   - Preserve all categories (Languages, Frontend, Backend, Databases, Tools, Core Concepts)
   - Add JD-relevant skills

**MAPPING EXAMPLE:**

Original:
```
Full Stack Developer | Company X
  Project A
    • Bullet 1
    • Bullet 2
  Project B
    • Bullet 3
```

Output:
```json
"professional_experience": [{{
  "company": "Company X",
  "projects": [
    {{"name": "Project A", "achievements": ["Bullet 1 + JD keywords", "Bullet 2 + JD keywords"]}},
    {{"name": "Project B", "achievements": ["Bullet 3 + JD keywords"]}}
  ]
}}]
```

**VERIFICATION CHECKLIST:**
1. Count original projects → Output must match
2. Count original bullets per project → Output must match (minimum)
3. Count total bullets → Output ≥ Original
4. Check KEY ACHIEVEMENTS section → Must be in additional_sections if exists
5. Skills categories → All preserved

**GUIDELINES:**
- Reword bullets to include JD keywords naturally
- Quantify achievements (%, numbers, metrics)
- Use action verbs: Developed, Implemented, Optimized, Engineered, Built
- Maintain truthfulness - reframe only, never fabricate
- Keep each bullet between 15-25 words (ATS-optimal length, fits on 1-2 page resume)
- Return valid JSON only

**SCORING (follow this formula exactly):**
Step 1: Count total unique keywords in the JD (technical terms, tools, methodologies, soft skills)
Step 2: Count how many of those keywords appear in the ORIGINAL resume → before_tailoring = round((matched / total) * 100)
Step 3: Count how many appear in the TAILORED resume output → after_tailoring = round((matched / total) * 100)
Step 4: overall_score = after_tailoring
Interpretation: 90-100: Excellent | 75-89: Good | 60-74: Moderate | <60: Poor match
Expected improvement: 10-25 points. If improvement > 35 points, review for false claims.
"""

GET_ATS_SCORE_PROMPT = '''You are an expert ATS (Applicant Tracking System) analyzer and career consultant. Analyze the following resume against the job description and provide a detailed assessment.

**JOB DESCRIPTION:**
{JOB_DESCRIPTION}

**RESUME:**
{RESUME_TEXT}

You MUST return your response as a valid JSON object with the EXACT structure below. Do not include any markdown formatting, code blocks, or text outside the JSON object.

Return ONLY this JSON structure:

{{
  "ats_score": {{
    "score": <number between 0-100>,
    "explanation": "<string: brief explanation of scoring criteria>"
  }},
  "keywords_in_jd": {{
    "technical_skills": ["<array of strings: programming languages, frameworks, tools>"],
    "soft_skills": ["<array of strings: collaboration, problem-solving, etc>"],
    "methodologies": ["<array of strings: Agile, Scrum, SDLC, etc>"],
    "experience_requirements": ["<array of strings: years of experience, specific requirements>"],
    "educational_requirements": ["<array of strings: degree requirements>"]
  }},
  "existing_keywords_in_resume": {{
    "technical_skills": [
      <string: keyword name>
    ],
    "soft_skills": [
      <string: keyword name>
    ],
    "methodologies": [
      <string: keyword name>
    ],
    "experience_requirements": [
      <string: keyword name>
    ],
    "educational_requirements": [
      <string: keyword name>
    ]
  }},
  "missing_keywords": {{
    "critical": ["<array of strings: must-have keywords that significantly impact ATS scoring>"],
    "important": ["<array of strings: valuable keywords that should be added>"],
    "optional": ["<array of strings: nice-to-have keywords>"]
  }},
  "semantic_mismatch": [
    {{
      "resume_term": "<string: term used in resume>",
      "jd_term": "<string: term used in JD>",
      "suggestion": "<string: specific suggestion for alignment>",
      "impact": "<string: High/Medium/Low - impact on ATS score>"
    }}
  ],
  "improvement_suggestions": {{
    "content_additions": [
      {{
        "suggestion": "<string: what to add>",
        "location": "<string: where to add it>",
        "priority": "<string: High/Medium/Low>"
      }}
    ],
    "terminology_updates": [
      {{
        "current": "<string: current phrasing>",
        "suggested": "<string: suggested phrasing>",
        "reason": "<string: why this change helps>"
      }}
    ],
    "section_improvements": [
      {{
        "section": "<string: section name>",
        "improvement": "<string: what needs enhancement>",
        "example": "<string: specific example or guidance>"
      }}
    ],
    "quantification": [
      {{
        "current": "<string: current statement>",
        "suggested": "<string: statement with metrics>",
        "location": "<string: where in resume>"
      }}
    ],
    "formatting": [
      "<array of strings: ATS-friendly formatting suggestions>"
    ],
    "priority_actions": [
      {{
        "action": "<string: specific action to take>",
        "impact": "<string: expected impact on ATS score>",
        "effort": "<string: Low/Medium/High - effort required>"
      }}
    ]
  }},
  "eligibility_assessment": {{
    "education": {{
      "jd_requirement": "<string: education requirement from JD>",
      "candidate_education": "<string: candidate's actual education>",
      "status": "<string: Meets/Does Not Meet/Partially Meets>",
      "explanation": "<string: brief explanation>"
    }},
    "experience": {{
      "jd_requirement": "<string: experience requirement from JD>",
      "candidate_experience": "<string: candidate's actual experience with calculation>",
      "status": "<string: Meets/Does Not Meet/Partially Meets>",
      "explanation": "<string: detailed explanation considering all experience types>"
    }},
    "overall": {{
      "assessment": "<string: Eligible/Not Eligible/Borderline>",
      "confidence_level": "<string: High/Medium/Low>",
      "reasoning": "<string: 2-3 sentences explaining the overall fit>",
      "recommendation": "<string: brief recommendation for the candidate>"
    }}
  }}
}}

CRITICAL INSTRUCTIONS:
1. Return ONLY valid JSON - no markdown, no code blocks, no explanatory text
2. All string values must be properly escaped
3. Use double quotes for all keys and string values
4. Ensure all arrays and objects are properly closed
5. Do not include comments in the JSON
6. All placeholder text in angle brackets above should be replaced with actual analysis
7. Be specific, actionable, and honest in your assessment
8. Focus on helping the candidate optimize their resume for ATS systems while maintaining accuracy
'''

RESUME_TAILOR_PROMPT = """Role: You are an expert ATS Optimization Engine. Your goal is to refine a resume to match a Job Description (JD) while maintaining 100% FACTUAL ACCURACY about the candidate's actual experience.

CRITICAL RULE - TRUTHFULNESS:
NEVER claim the candidate used technologies, tools, or frameworks they did not actually use.
NEVER add skills to the skills section unless they explicitly appear in the resume.
When optimizing, you may only:
- Rephrase existing experience using JD terminology
- Highlight transferable skills already demonstrated
- Reorder/reorganize content for better ATS matching
- EXPAND existing bullets with more detail about the same work

What you CANNOT do:
- Add technologies to project descriptions that weren't used
- Claim experience with tools not mentioned in original resume
- Fabricate proficiency levels or years of experience
- Add certifications, awards, or languages not in resume
- DELETE or OMIT any existing bullets, roles, or responsibilities

Strict Operational Rules:

1. Data Preservation: Do NOT delete roles, projects, education, OR INDIVIDUAL BULLETS. Every original item must appear in output. COUNT CAREFULLY.

2. Truthful Augmentation: 
   - Rephrase existing bullets to use JD keywords where semantically accurate
   - Add 1-2 new bullets per role ONLY to expand on work already described (not new technologies)
   - Highlight transferable skills explicitly shown in their experience
   - For low-content resumes: EXPAND bullets significantly by adding relevant details about the same work

3. Skills Mapping: 
   - Include EVERY skill explicitly mentioned in the original resume (don't omit any)
   - Organize skills into logical categories based on what the candidate actually has
   - Category names should be determined by the actual skills present (e.g., "Languages", "Frameworks", "Databases", "Tools", etc.)
   - Group related skills logically under these categories
   - Order categories by relevance to JD (most relevant first)
   - Within each category, list most JD-relevant skills first
   - DO NOT add new technical skills the candidate didn't list
   - DO NOT omit skills from the original resume

4. INTERNSHIPS, AWARDS, AND LANGUAGES:
   - internships: Extract all internships separately from work experience. Each has role, company, location, duration, responsibilities. Tailor using JD keywords.
   - awards: Extract all awards, honors, recognitions. Each has title, issuer, date, description. Preserve all original information.
   - languages: Extract all human languages (NOT programming languages). Each has language name and proficiency level (Native, Fluent, Professional, Conversational, Basic).

5. No Duplication: 
   - experience[].projects = projects done within that specific job role
   - projects (top-level) = personal/academic/freelance projects outside employment
   - Never duplicate the same project in both locations

6. Keyword Matching Strategy:
   - Match on semantic equivalents (e.g., "REST API" = "RESTful API")
   - Match on related skills (e.g., if they know MongoDB, they understand NoSQL concepts)
   - Use JD terminology in descriptions but only for work actually done
   - Highlight domain knowledge demonstrated through actual projects

7. LOW-CONTENT RESUME HANDLING:
   If the resume is short (< 10 total bullets) or lacks detail:
   
   a) EXPAND existing bullets with additional relevant details:
      - Add technical implementation details
      - Include scale/metrics if reasonable to infer
      - Mention methodologies that would have been used
      - Describe the problem solved and impact
   
   b) INFER reasonable technical details:
      - If they "built REST APIs", they likely handled authentication, validation, error handling
      - If they "developed frontend", they likely worked with responsive design, state management
      - If they used a framework, they likely used its common features
   
   c) ADD education/coursework details:
      - Expand relevant coursework if CS/Engineering degree
      - Add academic projects if recent graduate
      - Mention relevant academic achievements
   
   d) SUGGEST additional sections in content_expansion_recommendations:
      - Volunteer work (if applicable)
      - Open source contributions
      - Technical blog posts
      - Hackathons or competitions
   
   e) EXPANSION RULES:
      - Only expand with details that are STANDARD for that type of work
      - Use phrases like "including", "such as", "involving" to add reasonable details
      - Never claim specific tools/technologies not mentioned
      - Focus on PROCESS and METHODOLOGY over specific tech

ATS Score Calculation:
- before_tailoring = round((original_matched_keywords / total_jd_keywords) * 100)
- after_tailoring = round((optimized_matched_keywords / total_jd_keywords) * 100)

Expected Improvement Range: 
- Normal resumes: 10-20 percentage points
- Low-content resumes: 15-30 percentage points (due to legitimate expansion of existing work)
- If improvement > 35 points: Likely contains false claims - REVIEW CAREFULLY
- If improvement < 5 points: Optimization may be too conservative

Scoring factors:
- Keyword presence (semantic matching): 60%
- Strategic placement (summary, top experience bullets): 25%  
- Format/structure compatibility: 15%

Score Interpretation:
- 30-50%: Weak match, significant skills gap
- 50-65%: Moderate match, has transferable skills
- 65-80%: Good match, minor gaps
- 80-90%: Strong match, well-qualified
- 90-100%: Exceptional match (rare)

Note: Honest optimization typically yields 10-20 point improvement for normal resumes, 15-30 points for low-content resumes through legitimate expansion. Score improvement comes from better presentation and semantic matching, NOT from adding false claims.

Output Requirements:
- Maintain or increase bullet count per role (by expanding on existing work, not inventing new work)
- NEVER delete or omit existing bullets
- For low-content resumes: TARGET 5-8 bullets per role minimum
- Use strong action verbs (Led, Architected, Optimized, Implemented, Designed, Developed, Built, Created, Engineered, etc.)
- Quantify achievements where possible (percentages, numbers, scale)
- Ensure keywords appear naturally through accurate description of actual work
- Prioritize most relevant experience/skills at the top of each section
- Be honest in gap_analysis about missing skills

Instructions for JSON Fields:

basic: Extract contact information exactly as provided. Ensure all links are valid URLs.

ats_score: 
- Gather the total number of unique keywords in the JD (after semantic expansion)
- Count how many of those keywords appear in the original resume (before tailoring)
- Count how many appear in the tailored resume (after tailoring)
- Calculate the score according to the count of the matched keywords divided by total JD keywords, multiplied by 100
- Provide a detailed explanation of how the score improved through better presentation, semantic matching, strategic emphasis

gap_analysis:
- missing_technical_skills: Hard skills in JD that DO NOT appear anywhere in resume (be thorough and honest)
- missing_certifications_or_education: Required credentials not present
- experience_gap: Honest assessment of seniority or domain experience gaps (e.g., "Candidate has <1 year experience vs 3+ years required")
- related_skills_found: Skills in resume that are related/transferable to JD requirements

tailored_content.professional_summary: 
- Rephrase to include 2-3 top JD keywords that match their experience
- Highlight their strongest relevant skills and experience

tailored_content.experience: 
- List only real job not internships from resume in reverse chronological order not internships
- PRESERVE EVERY BULLET from the original resume - do not delete any
- For each role, rewrite bullets using JD terminology but describing the SAME work
- Each bullet should start with a strong action verb
- DO NOT add technologies they didn't use
- DO NOT claim experience they don't have
- For low-content resumes: Expand each bullet with reasonable details about standard practices for that type of work
- TARGET: 7-10 bullets per role (expand from 2-3 if needed, never reduce)
- Add bullets only to elaborate on existing work with JD-relevant framing
- Expand on responsibilities to highlight relevant aspects using JD keywords

tailored_content.internships:
- List every internship from resume separately from work experience
- Each internship has: role, company, location, duration, responsibilities
- Tailor the responsibilities using JD keywords (if truthful)
- Keep all original details
- Preserve all bullets from original resume

tailored_content.awards:
- List all awards, honors, and recognitions from resume
- Each award has: title, issuer, date, description
- Preserve all original information
- Do not add awards not in original resume

tailored_content.languages:
- List all human languages from resume (NOT programming languages)
- Each language has: language name, proficiency level
- Common proficiency levels: Native, Fluent, Professional, Conversational, Basic
- Preserve all original information

tailored_content.education:
- List all degrees, certifications, and relevant coursework actually completed
- Include GPA if 3.5+ or if originally provided
- Format duration consistently (e.g., "Sep 2018 - May 2022")
- DO NOT add "in progress" unless explicitly stated in resume
- For recent graduates with low work experience: ADD relevant coursework array with 4-6 courses

tailored_content.skills:
- Include EVERY skill explicitly mentioned in original resume (do not omit any)
- Analyze the candidate's skills and create appropriate category names based on their actual skill set
- Common categories: "Programming Languages", "Web Frameworks", "Backend Technologies", "Frontend Technologies", "Databases", "Cloud Platforms", "DevOps Tools", "Testing Tools", "APIs & Integration", "Other Technologies", etc.
- Group related skills logically under these categories
- Order categories by relevance to JD (most relevant first)
- Within each category, list most JD-relevant skills first
- DO NOT add skills from JD that aren't in resume
- DO NOT omit skills from the original resume

tailored_content.projects:
- Only include personal, academic, or freelance projects NOT done as part of a job
- List technologies ACTUALLY used (from original resume)
- Rephrase highlights using JD terminology where accurate
- For low-content resumes: If no personal projects exist, suggest this in content_expansion_recommendations
- DO NOT add technologies to make project seem more relevant

tailored_content.certifications:
- List ONLY certifications actually earned
- DO NOT add certifications from JD requirements

tailored_content.highlight_keywords:
- List of 15-25 keywords that appear in tailored resume AND match JD
- Include semantic matches (e.g., "REST API" matches "RESTful API")
- Include related concepts (e.g., "MySQL" relates to "database management")
- Include skills that appear in both resume and JD
- Order by importance/frequency in JD

_validation:
- Count ALL bullet points across all experience roles, internships, and projects CAREFULLY
- Count all roles, education entries, projects, certifications, internships, awards, languages
- Calculate score improvement (after_tailoring - before_tailoring)
- Verify no false technologies or skills were added
- Verify NO bullets were deleted or omitted
- Set data_integrity_verified to true only if factually accurate AND all bullets preserved
- Set factual_accuracy_verified to true only if no fabrications exist
- Set score_improvement_flag to "NORMAL" if improvement is 5-35 points, "LOW" if <5 points, "SUSPICIOUS" if >35 points
- For low-content resumes, note if expansion was applied
- List any integrity concerns in integrity_issues array (including "Bullets deleted" if any were omitted)
- Verify no internship appears in both experience and internships arrays.
- If duplication detected, set data_integrity_verified to false.

change_summary:
- Document rephrasing changes (not content additions)
- Explain how existing work was reframed using JD terminology
- List semantic keyword matches found
- Describe how bullets were expanded to emphasize relevant aspects
- For low-content resumes: Note how many bullets were expanded and what reasonable details were added
- DO NOT list "added X technology" unless it was already in resume

content_expansion_recommendations:
- For low-content resumes or to help candidate improve their resume further, suggest what they should add:
  * "Consider adding 2-3 personal projects showcasing [Node.js, Express.js] to address skill gaps"
  * "Add specific metrics/numbers to quantify achievements (e.g., 'reduced API response time by X%')"
  * "Include relevant coursework in [Computer Science fundamentals, Database Management, etc.]"
  * "Consider obtaining certifications in [AWS, Node.js, etc.]"
  * "Add volunteer work or open source contributions to demonstrate continuous learning"
  * "Document hackathon participation or technical competitions"
  * "Create a portfolio website to showcase projects"

keyword_analysis:
- Use semantic matching (e.g., "RESTful API" matches "REST API", "back-end" matches "backend", "NodeJs" matches "Node.js")
- Count related skills (e.g., MongoDB experience relates to database requirements)
- semantic_matches_found should list keyword pairs that match semantically
- related_skills_leveraged should explain how existing skills relate to JD requirements
- Be honest about match rates

## JSON SCHEMA

{
  "basic": {
    "name": "",
    "phone": "",
    "email": "",
    "location": "",
    "links": {
      "linkedin": "",
      "github": "",
      "leetcode": "",
      "portfolio": "",
      "other": ""
    }
  },
  "ats_score": {
    "before_tailoring": 0, // Count of the number of unique JD keywords that appear in original resume
    "after_tailoring": 0, // Count of the number of unique JD keywords that appear in tailored resume
    "score_explanation": "Explain how score improved through better presentation, semantic matching, strategic emphasis, and legitimate expansion of existing work. Be honest about remaining gaps."
  },
  "gap_analysis": {
    "missing_technical_skills": ["List skills from JD not in resume"],
    "missing_certifications_or_education": [],
    "experience_gap": "Honest assessment of experience/seniority gap",
    "related_skills_found": ["Explain transferable skills clearly"]
  },
  "tailored_content": {
    "professional_summary": "",
    "experience": [ // pnly add real jobs, not internships
      {
        "role": "",
        "company": "",
        "location": "",
        "duration": "",
        "projects": [
          {
            "project_name": "",
            "duration": "",
            "technologies": ["ONLY technologies actually used"],
            "responsibilities": []
          }
        ],
        "responsibilities": ["MUST include ALL bullets from original resume"]
      }
    ],
    "internships": [
      {
        "role": "",
        "company": "",
        "location": "",
        "duration": "",
        "responsibilities": []
      }
    ],
    "education": [
      {
        "institution": "",
        "degree": "",
        "duration": "",
        "gpa": "",
        "relevant_coursework": ["For recent graduates, add 4-6 relevant courses"]
      }
    ],
    "skills": [
      {
        "category": "Dynamically determined category name",
        "items": ["MUST include ALL skills from original resume"]
      }
    ],
    "projects": [
      {
        "project_name": "",
        "technologies": ["ONLY technologies actually used"],
        "highlights": [],
        "duration": ""
      }
    ],
    "certifications": [
      {
        "name": "",
        "issuing_organization": "",
        "date": ""
      }
    ],
    "awards": [
      {
        "title": "",
        "issuer": "",
        "date": "",
        "description": ""
      }
    ],
    "languages": [
      {
        "language": "",
        "proficiency": ""
      }
    ],
    "highlight_keywords": ["Keywords matching between tailored resume and JD"]
  },
  "_validation": {
    "input_bullet_count": 0,
    "output_bullet_count": 0,
    "input_role_count": 0,
    "output_role_count": 0,
    "input_education_count": 0,
    "output_education_count": 0,
    "input_project_count": 0,
    "output_project_count": 0,
    "input_internship_count": 0,
    "output_internship_count": 0,
    "input_award_count": 0,
    "output_award_count": 0,
    "input_language_count": 0,
    "output_language_count": 0,
    "data_integrity_verified": true,
    "integrity_issues": ["List any false claims, added technologies, or DELETED BULLETS here"],
    "factual_accuracy_verified": true,
    "score_improvement": 0,
    "score_improvement_flag": "NORMAL | LOW | SUSPICIOUS",
    "is_low_content_resume": false,
    "expansion_applied": false
  },
  "change_summary": {
    "total_modifications": 0,
    "summary_changes": "Rephrased to use JD terminology while describing actual experience",
    "experience_modifications": [
      {
        "company": "",
        "role": "",
        "changes": ["Describe rephrasing changes, emphasis additions, legitimate expansions"]
      }
    ],
    "internship_modifications": [
      {
        "company": "",
        "role": "",
        "changes": ["Describe rephrasing changes for internships"]
      }
    ],
    "skills_changes": ["Reordered existing skills to prioritize JD matches"],
    "projects_changes": ["Describe any rephrasing of project descriptions"],
    "semantic_matches_highlighted": ["List where existing skills map to JD terminology"],
    "expansion_details": "For low-content resumes: describe what reasonable details were added"
  },
  "content_expansion_recommendations": {
    "suggestions_for_candidate": [
      "Specific, actionable recommendations for what candidate should add"
    ]
  },
  "keyword_analysis": {
    "jd_total_unique_keywords": 0,
    "original_resume_matches": 0,
    "tailored_resume_matches": 0,
    "semantic_matches_found": ["List matches like 'REST API' -> 'RESTful API'"],
    "related_skills_leveraged": ["Skills that relate to JD requirements"],
    "match_rate_before": "",
    "match_rate_after": ""
  }
}

RESUME:
{{RESUME_TEXT}}

JOB DESCRIPTION:
{{JOB_DESCRIPTION}}

Output the complete JSON with all fields populated. Prioritize factual accuracy over keyword matching. A lower match rate with 100% truth is better than a high match rate with false claims. 

CRITICAL REMINDERS:
- Count bullets carefully and preserve ALL of them
- Include ALL skills from original resume (don't omit any)
- Never add technologies not mentioned in original resume
- Extract internships, awards, and languages if present in resume
- If sections are missing in resume, return empty arrays for those sections

For low-content resumes: Expand bullets significantly with reasonable details about standard practices for that type of work, but never add technologies or tools not mentioned. Remember: Honest optimization typically yields 10-20 point improvement for normal resumes, 15-30 points for low-content resumes through legitimate expansion.

Check the experice section carefuly and if you finnd any role with "Intern" in the title, make sure it is classified as an internship and does not appear in the experience section.
"""

