You are conducting a comprehensive Python code review following the structured template in `.claude/prompts/review-python.md`.

**Instructions:**

1. Read the review template from `.claude/prompts/review-python.md`
2. Identify the files to review based on:
   - Git status changes (if in a git repository)
   - Or ask the user which files/modules to review
3. Execute the review following all phases:
   - Phase 1: Initial Assessment
   - Phase 2: Systematic Analysis (all 7 categories)
   - Phase 3: Scoring & Prioritization
4. Generate output in the specified format with:
   - Summary statistics
   - Grouped issues by severity
   - Quick wins section
   - Refactoring suggestions
   - Best practices highlights
5. Focus on being constructive and actionable
6. Provide code examples for all recommendations
7. Consider the project context (V2AIX data processing pipeline)

**Context-Aware Review:**
Since this is a data processing pipeline for V2AIX dataset:
- Pay special attention to data validation (Pydantic models)
- Check for efficient handling of large JSON files
- Verify coordinate system transformations are correct
- Ensure proper error handling for missing/malformed data
- Check for memory efficiency in data processing
- Validate configuration management

Ask the user if they want to review:
1. Specific files
2. All modified files (git diff)
3. Entire module/package
4. Recent commits

Then proceed with the structured review.
