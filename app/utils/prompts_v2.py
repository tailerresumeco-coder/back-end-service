# =============================================================================
# PROMPT V2 - Single-Step Resume Processing
# One prompt: Resume + JD → Tailored JSON (with zero data loss)
# =============================================================================

RESUME_TAILOR_PROMPT = """You are an ATS resume parser and optimizer. Extract ALL data from the resume and tailor it for the job description.

## CRITICAL RULES - ZERO DATA LOSS

### 1. EXTRACT EVERYTHING (MOST IMPORTANT)
- Every bullet point in resume MUST appear in output
- Every skill mentioned MUST be extracted
- Every project MUST be captured
- Every certification MUST be listed
- COUNT all bullets and verify: output_bullets >= input_bullets

### 2. NO FABRICATION
- NEVER add skills not in resume
- NEVER invent metrics ("improved by 40%")
- NEVER add fake certifications or experiences
- Missing JD skills go in gap_analysis ONLY

### 3. TAILORING ALLOWED
- REPHRASE bullets using JD keywords (if truthful)
- REORDER skills by JD relevance (matched first)
- STRENGTHEN action verbs (used → implemented)
- SPLIT bullets if they have multiple achievements
- NEVER DELETE or MERGE bullets

### 4. EXPERIENCE STRUCTURE
- Group multiple projects under same company/role
- Each project has: project_name, duration, technologies, responsibilities
- Use "role" field, duration in "MMM YYYY – MMM YYYY" format

### 5. PROJECT CLASSIFICATION (STRICT - NO DUPLICATES)
- Experience section: ONLY work projects done at a company (part of job responsibilities)
- Projects section: ONLY personal, academic, side projects, or hackathon projects (NOT done at any employer)
- A project MUST appear in ONE section ONLY - NEVER IN BOTH
- If a project is mentioned under work experience (company/employer), DO NOT add it to the projects section
- If a project has no associated company/employer, it goes in projects section only

### 6. SKILLS EXTRACTION
Extract ALL skills from resume and organize into DYNAMIC categories based on actual content.
Create categories that best represent the resume's skills (examples below, but use what fits):
- Languages: Java, Python, JavaScript, TypeScript, SQL
- Frameworks: Spring Boot, React, Angular, Node.js, Express
- Databases: PostgreSQL, MongoDB, MySQL, Redis
- Cloud & DevOps: AWS, Docker, Kubernetes, CI/CD, Jenkins
- Tools: Git, Postman, Figma, Jira, VS Code
- Soft Skills: Problem Solving, Communication, Teamwork

IMPORTANT: Create as many or as few categories as needed based on the resume content.
Each category should have at least 2-3 items. Combine sparse categories if needed.

### 7. CHANGE TRACKING
For transparency, document all modifications made during tailoring:
- Track which bullets were rephrased and why
- List keywords injected from JD into content
- Note action verbs that were strengthened
- Summarize changes made to each section

## ATS SCORE
Score = (Matched JD Keywords / Total JD Keywords) × 100

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
      "other": ""
    }
  },
  "ats_score": {
    "before_tailoring": 0,
    "after_tailoring": 0,
    "score_explanation": ""
  },
  "gap_analysis": {
    "missing_technical_skills": [],
    "missing_certifications_or_education": [],
    "experience_gap": "",
    "related_skills_found": []
  },
  "tailored_content": {
    "professional_summary": "",
    "experience": [
      {
        "role": "",
        "company": "",
        "location": "",
        "duration": "",
        "projects": [
          {
            "project_name": "",
            "duration": "",
            "technologies": [],
            "responsibilities": []
          }
        ]
      }
    ],
    "education": [
      {
        "institution": "",
        "degree": "",
        "duration": "",
        "gpa": ""
      }
    ],
    "skills": [
      {
        "category": "Languages",
        "items": []
      },
      {
        "category": "Frameworks",
        "items": []
      }
    ],
    "projects": [
      {
        "project_name": "",
        "technologies": [],
        "highlights": []
      }
    ],
    "certifications": [],
    "highlight_keywords": []
  },
  "_validation": {
    "input_bullet_count": 0,
    "output_bullet_count": 0,
    "data_integrity_verified": true
  },
  "change_summary": {
    "total_modifications": 0,
    "summary_changes": "Description of changes made to professional summary",
    "experience_modifications": [
      {
        "company": "Company Name",
        "changes": ["Rephrased bullet to include keyword X", "Strengthened action verb from Y to Z"]
      }
    ],
    "skills_changes": ["Reordered skills to prioritize JD-matching ones", "Grouped related skills"],
    "keywords_injected": ["keyword1", "keyword2"]
  }
}

## BEFORE OUTPUT - VERIFY:
☐ Every resume bullet is in output
☐ output_bullet_count >= input_bullet_count
☐ No skills added that weren't in resume
☐ Missing JD skills are in gap_analysis only
☐ change_summary accurately reflects all modifications made

Return ONLY valid JSON. No markdown.

RESUME:
{{RESUME_TEXT}}

JOB DESCRIPTION:
{{JOB_DESCRIPTION}}
"""
