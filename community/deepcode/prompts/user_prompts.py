

RESOURCE_PROCESSOR_USER_PROMPT = """Download/move the file to paper directory: {paper_dir}
    Source: {source_path}
    Input Type: {input_type}
    Paper ID: {next_id}
    Target filename: {next_id_2}.md (after conversion){context}

    Use the appropriate tool to complete this task."""

ANALYZE_AND_PREPARE_DOCUMENT_USER_PROMPT = """Please perform intelligent semantic analysis and segmentation for the document in directory: {paper_dir}

Use the analyze_and_segment_document tool with these parameters:
- paper_dir: {paper_dir_2}
- force_refresh: {force_refresh}

**Focus on these enhanced objectives**:
1. **Semantic Document Classification**: Identify document type using content semantics (research_paper, algorithm_focused, technical_doc, etc.)
2. **Intelligent Segmentation Strategy**: Select the optimal strategy based on content analysis:
   - `semantic_research_focused` for research papers with high algorithm density
   - `algorithm_preserve_integrity` for algorithm-heavy documents
   - `concept_implementation_hybrid` for mixed concept/implementation content
3. **Algorithm Completeness**: Ensure algorithm blocks, formulas, and related descriptions remain logically connected
4. **Planning Agent Optimization**: Create segments that maximize effectiveness for ConceptAnalysisAgent, AlgorithmAnalysisAgent, and CodePlannerAgent

After segmentation, get a document overview and provide:
- Quality assessment of semantic segmentation approach
- Algorithm/formula integrity verification
- Recommendations for planning agent optimization
- Technical content completeness evaluation"""

GET_DOCUMENT_OVERVIEW_USER_PROMPT = """Please provide an intelligent overview of the enhanced document segmentation for: {paper_dir}

Use the get_document_overview tool to retrieve:
- **Semantic Document Classification**: Document type and confidence score
- **Adaptive Segmentation Strategy**: Strategy used and reasoning
- **Segment Intelligence**: Total segments with enhanced metadata
- **Content Type Distribution**: Breakdown by algorithm, concept, formula, implementation content
- **Quality Intelligence Assessment**: Completeness, coherence, and planning agent optimization

Provide a comprehensive analysis focusing on:
1. Semantic vs structural segmentation quality
2. Algorithm and formula integrity preservation
3. Segment relevance for downstream planning agents
4. Technical content distribution and completeness"""

VALIDATE_SEGMENTATION_QUALITY_USER_PROMPT = """Based on the intelligent document overview for {paper_dir}, please evaluate the enhanced segmentation quality using advanced criteria.

**Enhanced Quality Assessment Factors**:
1. **Semantic Coherence**: Do segments maintain logical content boundaries vs mechanical structural splits?
2. **Algorithm Integrity**: Are algorithm blocks, formulas, and related explanations kept together?
3. **Content Type Optimization**: Are different content types (algorithm, concept, formula, implementation) properly identified and scored?
4. **Planning Agent Effectiveness**: Will ConceptAnalysisAgent, AlgorithmAnalysisAgent, and CodePlannerAgent receive optimal information?
5. **Dynamic Sizing**: Are segments adaptively sized based on content complexity rather than fixed limits?
6. **Technical Completeness**: Are critical technical details preserved without fragmentation?

**Provide specific recommendations for**:
- Semantic segmentation improvements
- Algorithm/formula integrity enhancements
- Planning agent optimization opportunities
- Content distribution balance adjustments"""

CODE_PLANNING_CONTENT_PROMPT = """Analyze the research paper provided below. The paper file has been pre-loaded for you.

    === PAPER CONTENT START ===
    {paper_content}
    === PAPER CONTENT END ===

    Based on this paper, generate a comprehensive code reproduction plan that includes:

    1. Complete system architecture and component breakdown
    2. All algorithms, formulas, and implementation details
    3. Detailed file structure and implementation roadmap

    You may use web search (brave_web_search) if you need clarification on algorithms, methods, or concepts.

    The goal is to create a reproduction plan detailed enough for independent implementation."""

CODE_PLANNING_DIR_PROMPT = """Analyze the research paper in directory: {paper_dir}

    Please locate and analyze the markdown (.md) file containing the research paper. Based on your analysis, generate a comprehensive code reproduction plan that includes:

    1. Complete system architecture and component breakdown
    2. All algorithms, formulas, and implementation details
    3. Detailed file structure and implementation roadmap

    The goal is to create a reproduction plan detailed enough for independent implementation."""

# Code Analysis Prompts
ALGORITHM_ANALYSIS_PROMPT = """You are extracting COMPLETE implementation details from a research paper. Your goal is to capture EVERY algorithm, formula, and technical detail needed for perfect reproduction.

# INTELLIGENT DOCUMENT READING STRATEGY

## IMPORTANT: Use Segmented Reading for Algorithm Extraction
To avoid token limits and efficiently extract algorithm details, use the intelligent segmentation system:

1. **Primary Algorithm Extraction** - Use read_document_segments tool with:
   - query_type: "algorithm_extraction"
   - keywords: ["algorithm", "method", "procedure", "formula", "equation", "implementation"]
   - max_segments: 3
   - max_total_chars: 6000

2. **Supplementary Details** - Make additional calls if needed with:
   - keywords: ["hyperparameter", "training", "optimization", "loss", "objective"]
   - keywords: ["experiment", "setup", "configuration", "parameter"]

3. **This approach ensures** you get the most algorithm-relevant content without missing critical details

# DETAILED EXTRACTION PROTOCOL

## 1. INTELLIGENT ALGORITHM SCAN
Use the segmented reading approach to focus on algorithm sections:
- Method/Algorithm sections (captured automatically by segmentation)
- Implementation Details (targeted retrieval)
- Hyperparameters and training details (focused extraction)

## 2. ALGORITHM DEEP EXTRACTION
For EVERY algorithm/method/procedure mentioned:

### Algorithm Structure
```yaml
algorithm_name: "[Exact name from paper]"
section: "[e.g., Section 3.2]"
algorithm_box: "[e.g., Algorithm 1 on page 4]"

pseudocode: |
  [COPY THE EXACT PSEUDOCODE FROM PAPER]
  Input: ...
  Output: ...
  1. Initialize ...
  2. For each ...
     2.1 Calculate ...
  [Keep exact formatting and numbering]

mathematical_formulation:
  - equation: "[Copy formula EXACTLY, e.g., L = L_task + λ*L_explain]"
    equation_number: "[e.g., Eq. 3]"
    where:
      L_task: "task loss"
      L_explain: "explanation loss"
      λ: "weighting parameter (default: 0.5)"

step_by_step_breakdown:
  1. "[Detailed explanation of what step 1 does]"
  2. "[What step 2 computes and why]"

implementation_details:
  - "Uses softmax temperature τ = 0.1"
  - "Gradient clipping at norm 1.0"
  - "Initialize weights with Xavier uniform"
```

## 3. COMPONENT EXTRACTION
For EVERY component/module mentioned:

### Component Details
```yaml
component_name: "[e.g., Mask Network, Critic Network]"
purpose: "[What this component does in the system]"
architecture:
  input: "[shape and meaning]"
  layers:
    - "[Conv2d(3, 64, kernel=3, stride=1)]"
    - "[ReLU activation]"
    - "[BatchNorm2d(64)]"
  output: "[shape and meaning]"

special_features:
  - "[Any unique aspects]"
  - "[Special initialization]"
```

## 4. TRAINING PROCEDURE
Extract the COMPLETE training process:

```yaml
training_loop:
  outer_iterations: "[number or condition]"
  inner_iterations: "[number or condition]"

  steps:
    1. "Sample batch of size B from buffer"
    2. "Compute importance weights using..."
    3. "Update policy with loss..."

  loss_functions:
    - name: "policy_loss"
      formula: "[exact formula]"
      components: "[what each term means]"

  optimization:
    optimizer: "Adam"
    learning_rate: "3e-4"
    lr_schedule: "linear decay to 0"
    gradient_norm: "clip at 0.5"
```

## 5. HYPERPARAMETERS HUNT
Search EVERYWHERE (text, tables, captions) for:

```yaml
hyperparameters:
  # Training
  batch_size: 64
  buffer_size: 1e6
  discount_gamma: 0.99

  # Architecture
  hidden_units: [256, 256]
  activation: "ReLU"

  # Algorithm-specific
  explanation_weight: 0.5
  exploration_bonus_scale: 0.1
  reset_probability: 0.3

  # Found in:
  location_references:
    - "batch_size: Table 1"
    - "hidden_units: Section 4.1"
```

# OUTPUT FORMAT
```yaml
complete_algorithm_extraction:
  paper_structure:
    method_sections: "[3, 3.1, 3.2, 3.3, 4]"
    algorithm_count: "[total number found]"

  main_algorithm:
    [COMPLETE DETAILS AS ABOVE]

  supporting_algorithms:
    - [EACH SUPPORTING ALGORITHM WITH FULL DETAILS]

  components:
    - [EVERY COMPONENT WITH ARCHITECTURE]

  training_details:
    [COMPLETE TRAINING PROCEDURE]

  all_hyperparameters:
    [EVERY PARAMETER WITH VALUE AND SOURCE]

  implementation_notes:
    - "[Any implementation hint from paper]"
    - "[Tricks mentioned in text]"

  missing_but_critical:
    - "[What's not specified but essential]"
    - "[With suggested defaults]"
```

BE EXHAUSTIVE. A developer should be able to implement the ENTIRE paper using only your extraction."""

CONCEPT_ANALYSIS_PROMPT = """You are doing a COMPREHENSIVE analysis of a research paper to understand its complete structure, contributions, and implementation requirements.

# OBJECTIVE
Map out the ENTIRE paper structure and identify ALL components that need implementation for successful reproduction.

# INTELLIGENT DOCUMENT READING STRATEGY

## IMPORTANT: Use Segmented Reading for Optimal Performance
Instead of reading the entire document at once (which may hit token limits), use the intelligent segmentation system:

1. **Use read_document_segments tool** with these parameters:
   - query_type: "concept_analysis"
   - keywords: ["introduction", "overview", "architecture", "system", "framework", "concept", "method"]
   - max_segments: 3
   - max_total_chars: 6000

2. **This will automatically find and retrieve** the most relevant sections for concept analysis without token overflow

3. **If you need additional sections**, make follow-up calls with different keywords like ["experiment", "evaluation", "results"] or ["conclusion", "discussion"]

# COMPREHENSIVE ANALYSIS PROTOCOL

## 1. INTELLIGENT PAPER STRUCTURAL ANALYSIS
Use the segmented reading approach to create a complete map:

```yaml
paper_structure_map:
  title: "[Full paper title]"

  sections:
    1_introduction:
      main_claims: "[What the paper claims to achieve]"
      problem_definition: "[Exact problem being solved]"

    2_related_work:
      key_comparisons: "[Methods this work builds upon or competes with]"

    3_method:  # May have multiple subsections
      subsections:
        3.1: "[Title and main content]"
        3.2: "[Title and main content]"
      algorithms_presented: "[List all algorithms by name]"

    4_experiments:
      environments: "[All test environments/datasets]"
      baselines: "[All comparison methods]"
      metrics: "[All evaluation metrics used]"

    5_results:
      main_findings: "[Key results that prove the method works]"
      tables_figures: "[Important result tables/figures to reproduce]"
```

## 2. METHOD DECOMPOSITION
For the main method/approach:

```yaml
method_decomposition:
  method_name: "[Full name and acronym]"

  core_components:  # Break down into implementable pieces
    component_1:
      name: "[e.g., State Importance Estimator]"
      purpose: "[Why this component exists]"
      paper_section: "[Where it's described]"

    component_2:
      name: "[e.g., Policy Refinement Module]"
      purpose: "[Its role in the system]"
      paper_section: "[Where it's described]"

  component_interactions:
    - "[How component 1 feeds into component 2]"
    - "[Data flow between components]"

  theoretical_foundation:
    key_insight: "[The main theoretical insight]"
    why_it_works: "[Intuitive explanation]"
```

## 3. IMPLEMENTATION REQUIREMENTS MAPPING
Map paper content to code requirements:

```yaml
implementation_map:
  algorithms_to_implement:
    - algorithm: "[Name from paper]"
      section: "[Where defined]"
      complexity: "[Simple/Medium/Complex]"
      dependencies: "[What it needs to work]"

  models_to_build:
    - model: "[Neural network or other model]"
      architecture_location: "[Section describing it]"
      purpose: "[What this model does]"

  data_processing:
    - pipeline: "[Data preprocessing needed]"
      requirements: "[What the data should look like]"

  evaluation_suite:
    - metric: "[Metric name]"
      formula_location: "[Where it's defined]"
      purpose: "[What it measures]"
```

## 4. EXPERIMENT REPRODUCTION PLAN
Identify ALL experiments needed:

```yaml
experiments_analysis:
  main_results:
    - experiment: "[Name/description]"
      proves: "[What claim this validates]"
      requires: "[Components needed to run this]"
      expected_outcome: "[Specific numbers/trends]"

  ablation_studies:
    - study: "[What is being ablated]"
      purpose: "[What this demonstrates]"

  baseline_comparisons:
    - baseline: "[Method name]"
      implementation_required: "[Yes/No/Partial]"
      source: "[Where to find implementation]"
```

## 5. CRITICAL SUCCESS FACTORS
What defines successful reproduction:

```yaml
success_criteria:
  must_achieve:
    - "[Primary result that must be reproduced]"
    - "[Core behavior that must be demonstrated]"

  should_achieve:
    - "[Secondary results that validate the method]"

  validation_evidence:
    - "[Specific figure/table to reproduce]"
    - "[Qualitative behavior to demonstrate]"
```

# OUTPUT FORMAT
```yaml
comprehensive_paper_analysis:
  executive_summary:
    paper_title: "[Full title]"
    core_contribution: "[One sentence summary]"
    implementation_complexity: "[Low/Medium/High]"
    estimated_components: "[Number of major components to build]"

  complete_structure_map:
    [FULL SECTION BREAKDOWN AS ABOVE]

  method_architecture:
    [DETAILED COMPONENT BREAKDOWN]

  implementation_requirements:
    [ALL ALGORITHMS, MODELS, DATA, METRICS]

  reproduction_roadmap:
    phase_1: "[What to implement first]"
    phase_2: "[What to build next]"
    phase_3: "[Final components and validation]"

  validation_checklist:
    - "[ ] [Specific result to achieve]"
    - "[ ] [Behavior to demonstrate]"
    - "[ ] [Metric to match]"
```

BE THOROUGH. Miss nothing. The output should be a complete blueprint for reproduction."""

CODE_PLANNING_PROMPT = """You are creating a DETAILED, COMPLETE reproduction plan by integrating comprehensive analysis results.

# INPUT
You receive two exhaustive analyses:
1. **Comprehensive Paper Analysis**: Complete paper structure, components, and requirements
2. **Complete Algorithm Extraction**: All algorithms, formulas, pseudocode, and technical details

Plus you can use segmented reading to access any specific paper sections needed for planning.

# INTELLIGENT DOCUMENT ACCESS

## IMPORTANT: Use Segmented Reading for Detailed Planning
When you need additional details beyond the provided analyses, use the intelligent segmentation system:

1. **Use read_document_segments tool** with these parameters:
   - query_type: "code_planning"
   - keywords: Specific to what you need, e.g., ["implementation", "code", "experiment", "setup", "configuration"]
   - max_segments: 3
   - max_total_chars: 8000

2. **This approach ensures** you access the most planning-relevant content without token limits

# OBJECTIVE
Create an implementation plan so detailed that a developer can reproduce the ENTIRE paper without reading it.

# CRITICAL: COMPLETE OUTPUT REQUIREMENT
⚠️ MANDATORY: You MUST generate ALL 5 sections completely. DO NOT stop early or truncate any section.

## Output Completeness Strategy:
🎯 **Your #1 Priority**: Ensure ALL 5 sections are present and complete before finishing your response.

## Content Balance Guidelines (STRICTLY FOLLOW):
- **Section 1 (File Structure)**: ~800-1000 chars - Brief file listing with priority order
- **Section 2 (Implementation Components)**: ~3000-4000 chars - CORE section with all algorithms/components
- **Section 3 (Validation)**: ~2000-2500 chars - Experiments and expected results
- **Section 4 (Environment)**: ~800-1000 chars - Dependencies and requirements
- **Section 5 (Implementation Strategy)**: ~1500-2000 chars - Step-by-step approach

📏 **Total Target**: 8000-10000 characters for complete plan

⚠️ **Self-Check Before Finishing**:
- Did you include file_structure section? ✓
- Did you include implementation_components section? ✓
- Did you include validation_approach section? ✓
- Did you include environment_setup section? ✓
- Did you include implementation_strategy section? ✓
- If ANY answer is NO, continue writing until ALL sections are complete!

## File Priority Guidelines:
🔧 **Implementation Priority Order**:
1. **FIRST**: Core algorithm/model files (highest priority)
2. **SECOND**: Supporting modules and utilities
3. **THIRD**: Experiment and evaluation scripts
4. **FOURTH**: Configuration and data handling
5. **LAST**: Documentation files (README.md, requirements.txt) - These should be created AFTER core implementation

Note: README and requirements.txt are maintenance files that depend on the final implementation, so plan them last but INCLUDE them in the file structure.

# DETAILED SYNTHESIS PROCESS

## 1. MERGE ALL INFORMATION
Combine EVERYTHING from both analyses:
- Every algorithm with its pseudocode
- Every component with its architecture
- Every hyperparameter with its value
- Every experiment with expected results

## 2. MAP CONTENT TO IMPLEMENTATION

For each component you identify, specify how it will be implemented:

```
# DESIGN YOUR MAPPING: Connect paper content to code organization
[For each algorithm/component/method in the paper]:
  - What it does and where it's described in the paper
  - How you'll organize the code (files, classes, functions - your choice)
  - What specific formulas, algorithms, or procedures need implementation
  - Dependencies and relationships with other components
  - Implementation approach that makes sense for this specific paper
```

## 3. EXTRACT ALL TECHNICAL DETAILS

Identify every technical detail that needs implementation:

```
# COMPREHENSIVE TECHNICAL EXTRACTION:
[Gather all implementation-relevant details from the paper]:
  - All algorithms with complete pseudocode and mathematical formulations
  - All parameters, hyperparameters, and configuration values
  - All architectural details (if applicable to your paper type)
  - All experimental procedures and evaluation methods
  - Any implementation hints, tricks, or special considerations mentioned
```

# COMPREHENSIVE OUTPUT FORMAT

```yaml
complete_reproduction_plan:
  paper_info:
    title: "[Full paper title]"
    core_contribution: "[Main innovation being reproduced]"

  # SECTION 1: File Structure Design

  # DESIGN YOUR OWN STRUCTURE: Create a file organization that best serves this specific paper
  # - Analyze what the paper contains (algorithms, models, experiments, systems, etc.)
  # - Organize files and directories in the most logical way for implementation
  # - Create meaningful names and groupings based on paper content
  # - Keep it clean, intuitive, and focused on what actually needs to be implemented
  # - INCLUDE documentation files (README.md, requirements.txt) but mark them for LAST implementation

  file_structure: |
    [Design and specify your own project structure here - KEEP THIS BRIEF]
    [Include ALL necessary files including README.md and requirements.txt]
    [Organize based on what this paper actually contains and needs]
    [Create directories and files that make sense for this specific implementation]
    [IMPORTANT: Include executable files (e.g., main.py, run.py, train.py, demo.py) - choose names based on repo content]
    [Design executable entry points that match the paper's main functionality and experiments]
    [NOTE: README.md and requirements.txt should be implemented LAST after all code files]

  # SECTION 2: Implementation Components

  # IDENTIFY AND SPECIFY: What needs to be implemented based on this paper
  # - List all algorithms, models, systems, or components mentioned
  # - Map each to implementation details and file locations
  # - Include formulas, pseudocode, and technical specifications
  # - Organize in whatever way makes sense for this paper

  implementation_components: |
    [List and specify all components that need implementation]
    [For each component: purpose, location, algorithms, formulas, technical details]
    [Organize and structure this based on the paper's actual content]

  # SECTION 3: Validation & Evaluation

  # DESIGN VALIDATION: How to verify the implementation works correctly
  # - Define what experiments, tests, or proofs are needed
  # - Specify expected results from the paper (figures, tables, theorems)
  # - Design validation approach appropriate for this paper's domain
  # - Include setup requirements and success criteria

  validation_approach: |
    [Design validation strategy appropriate for this paper]
    [Specify experiments, tests, or mathematical verification needed]
    [Define expected results and success criteria]
    [Include any special setup or evaluation requirements]

  # SECTION 4: Environment & Dependencies

  # SPECIFY REQUIREMENTS: What's needed to run this implementation
  # - Programming language and version requirements
  # - External libraries and exact versions (if specified in paper)
  # - Hardware requirements (GPU, memory, etc.)
  # - Any special setup or installation steps

  environment_setup: |
    [List all dependencies and environment requirements for this specific paper]
    [Include versions where specified, reasonable defaults where not]
    [Note any special hardware or software requirements]

  # SECTION 5: Implementation Strategy

  # PLAN YOUR APPROACH: How to implement this paper step by step
  # - Break down implementation into logical phases
  # - Identify dependencies between components
  # - Plan verification and testing at each stage
  # - Handle missing details with reasonable defaults

  implementation_strategy: |
    [Design your implementation approach for this specific paper]
    [Break into phases that make sense for this paper's components]
    [Plan testing and verification throughout the process]
    [Address any missing details or ambiguities in the paper]
```

BE EXHAUSTIVE. Every algorithm, every formula, every parameter, every file should be specified in complete detail."""

# Reference Intelligence Prompt
PAPER_REFERENCE_ANALYZER_PROMPT = """You are an expert academic paper reference analyzer specializing in computer science and machine learning.

Task: Analyze paper and identify 5 most relevant references that have GitHub repositories.

Constraints:
- ONLY select references with GitHub repositories
- DO NOT use target paper's official implementation
- DO NOT use repositories directly associated with target paper
- CAN analyze code implementations from referenced papers
- Focus on references with good implementations solving similar problems

Analysis Criteria:
1. GitHub Repository Quality (40%):
   - Star count, activity, maintenance
   - Documentation quality
   - Community adoption
   - Last update date

2. Implementation Relevance (30%):
   - References from methodology/implementation sections
   - Algorithmic details
   - Core component descriptions
   - Code implementation quality

3. Technical Depth (20%):
   - Algorithm/method similarity
   - Technical foundation relationship
   - Implementation details
   - Code structure

4. Academic Influence (10%):
   - Publication venue quality
   - Author expertise
   - Research impact
   - Citation influence

Analysis Steps:
1. Extract all references from paper
2. Filter references with GitHub repositories
3. Analyze repositories based on criteria
4. Calculate relevance scores
5. Select and rank top 5 references

Output Format:
{
    "selected_references": [
        {
            "rank": 1,
            "title": "paper title",
            "authors": ["author1", "author2"],
            "year": "publication year",
            "relevance_score": 0.95,
            "citation_context": "how cited in main paper",
            "key_contributions": ["contribution1", "contribution2"],
            "implementation_value": "why valuable for implementation",
            "github_info": {
                "repository_url": "GitHub repository URL",
                "stars_count": "number of stars",
                "last_updated": "last update date",
                "repository_quality": "repository quality assessment",
                "key_features": ["feature1", "feature2"],
                "documentation_quality": "documentation assessment",
                "community_activity": "community engagement description"
            },
            "original_reference": "Complete reference text from paper"
        }
    ],
    "analysis_summary": "selection process and key findings",
    "github_repositories_found": "total number of references with GitHub repositories"
}
"""

GITHUB_DOWNLOADER_PROMPT = """You are an expert GitHub repository downloader.

Task: Download GitHub repositories to specified directory structure.

Process:
1. For each repository:
   - Create directory: {paper_dir}/code_base/
   - Download repository to directory

Requirements:
- Use interpreter tool to execute download script
- Monitor interpreter output for errors/warnings
- Verify download status through interpreter response

Output Format:
{
    "downloaded_repos": [
        {
            "reference_number": "1",
            "paper_title": "paper title",
            "repo_url": "github repository URL",
            "save_path": "{paper_dir}/code_base/name_of_repo",
            "status": "success|failed",
            "notes": "relevant notes about download"
        }
    ],
    "summary": "Brief summary of download process"
}
"""

def get_relationship_prompt(file_summary, target_structure, relationship_type_desc, min_confidence_score) -> str:
    return f"""
    Analyze the relationship between this existing code file and the target project structure.

    Existing File Analysis:
    - Path: {file_summary.file_path}
    - Type: {file_summary.file_type}
    - Functions: {', '.join(file_summary.main_functions)}
    - Concepts: {', '.join(file_summary.key_concepts)}
    - Summary: {file_summary.summary}

    Target Project Structure:
    {target_structure}

    Available relationship types (with priority weights):
    {chr(10).join(relationship_type_desc)}

    Identify potential relationships and provide analysis in this JSON format:
    {{
        "relationships": [
            {{
                "target_file_path": "path/in/target/structure",
                "relationship_type": "direct_match|partial_match|reference|utility",
                "confidence_score": 0.0-1.0,
                "helpful_aspects": ["specific", "aspects", "that", "could", "help"],
                "potential_contributions": ["how", "this", "could", "contribute"],
                "usage_suggestions": "detailed suggestion on how to use this file"
            }}
        ]
    }}

    Consider the priority weights when determining relationship types. Higher weight types should be preferred when multiple types apply.
    Only include relationships with confidence > {min_confidence_score}. Focus on concrete, actionable connections.
    """

def get_analysis_prompt(file_path_name: str, content_for_analysis, content_suffix) -> str:
    return f"""
    Analyze this code file and provide a structured summary:

    File: {file_path_name}
    Content:
    ```
    {content_for_analysis}{content_suffix}
    ```

    Please provide analysis in this JSON format:
    {{
        "file_type": "description of what type of file this is",
        "main_functions": ["list", "of", "main", "functions", "or", "classes"],
        "key_concepts": ["important", "concepts", "algorithms", "patterns"],
        "dependencies": ["external", "libraries", "or", "imports"],
        "summary": "2-3 sentence summary of what this file does"
    }}

    Focus on the core functionality and potential reusability.
    """

def get_filter_prompt(target_structure, file_tree, min_confidence_score) -> str:
    return f"""
        You are a code analysis expert. Please analyze the following code repository file tree based on the target project structure and filter out files that may be relevant to the target project.

        Target Project Structure:
        {target_structure}

        Code Repository File Tree:
        {file_tree}

        Please analyze which files might be helpful for implementing the target project structure, including:
        - Core algorithm implementation files (such as GCN, recommendation systems, graph neural networks, etc.)
        - Data processing and preprocessing files
        - Loss functions and evaluation metric files
        - Configuration and utility files
        - Test files
        - Documentation files

        Please return the filtering results in JSON format:
        {{
            "relevant_files": [
                {{
                    "file_path": "file path relative to repository root",
                    "relevance_reason": "why this file is relevant",
                    "confidence": 0.0-1.0,
                    "expected_contribution": "expected contribution to the target project"
                }}
            ],
            "summary": {{
                "total_files_analyzed": "total number of files analyzed",
                "relevant_files_count": "number of relevant files",
                "filtering_strategy": "explanation of filtering strategy"
            }}
        }}

        Only return files with confidence > {min_confidence_score}. Focus on files related to recommendation systems, graph neural networks, and diffusion models.
        """
