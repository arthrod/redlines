# Redlines Enhancement - Product Requirements Document

## 1. Introduction

**Request:** Generate PRD to implement: (1) structured diff output in JSON format with change type, (2) when creating redlines (output) of docx, use proper XML syntax of track changes, (3) make the standard class to follow FastAPI exposure logic, (4) add "red-blue" style to available styles, (5) modify intermediary format from markdown to HTML, (6) docling's HTML export + xmldiff's intelligent formatting handling is the right architecture, (7) maintain the diff backend used, but add and change it to the default option, xmldiff to use the diffs.

**Objective:** Enhance the redlines library with advanced diffing capabilities using xmldiff, add structured JSON output, implement proper DOCX track changes XML syntax, add FastAPI support, introduce red-blue styling, and transition from Markdown to HTML as the intermediary format while maintaining backward compatibility.

**Context:** The current redlines library uses SequenceMatcher for text diffs with Markdown as the intermediary format. This enhancement will modernize the architecture to use xmldiff for intelligent formatting-aware diffs, leverage docling's HTML export capabilities, provide structured output formats, and enable API-first usage patterns while maintaining the existing functionality for backward compatibility.

## 2. Repository Analysis

**Tech Stack:**
- Language: Python >=3.10
- Testing: pytest >=7.4.2, pytest-cov >=3.0.0
- CLI: typer[all] >=0.12.3
- Core dependencies: rich >=13.3.5, mistune >=3.1.4, beautifulsoup4 >=4.12.2, markdownify >=0.11.6
- Optional dependencies:
  - DOCX: python-docx >=1.1.0, html-for-docx >=0.6.0, docling ==2.48.0
  - PDF: weasyprint >=66.0, pypdf >=3.1.0
- Build system: hatchling >=1.18.0

**Architectural Patterns Observed:**
- **Processor pattern**: `WholeDocumentProcessor`, `DOCXProcessor`, `HTMLProcessor`, `MarkdownProcessor`, `PDFProcessor` - modular conversion pipeline
- **Async orchestration**: Heavy use of `asyncio.to_thread` and semaphore-based concurrency control
- **Manager pattern**: `ConversionManager` acts as a facade coordinating all format conversions
- **Markdown as pivot format**: All conversions funnel through Markdown as intermediate representation
- **Styles configuration**: `Styles` class provides centralized document styling across all processors
- **Progressive fallbacks**: Multiple backends tried in order (docling → markitdown → python-docx)

**Coding Standards:**
- Type hints with `from __future__ import annotations`
- Dataclasses for structured data (`@dataclass` with `slots=True` for efficiency)
- Abstract base classes for extensibility (`ABC`, `@abstractmethod`)
- Comprehensive docstrings with examples in all public methods
- Semantic error messages with clear guidance
- Defensive programming with try-except and optional dependency handling

**Testing Framework:**
- pytest with parametrized tests (`@pytest.mark.parametrize`)
- Coverage tracking via pytest-cov
- Tests organized by module: `test_redline.py`, `test_conversion_manager.py`, `test_docx_processor.py`
- Stub/mock patterns for external dependencies
- Async test support with `asyncio.run()`

## 3. Scope Definition

**In Scope:**

1. **JSON Structured Output** - Add `output_json` property returning structured diff with change types
2. **DOCX Track Changes XML** - Implement proper Office Open XML track changes syntax
3. **FastAPI Integration** - Create `RedlinesAPI` class with Pydantic models
4. **Red-Blue Style** - Add "red-blue" to markdown style options
5. **HTML Intermediary Format** - Transition from Markdown to HTML as pivot format
6. **xmldiff Integration** - Add xmldiff backend for intelligent HTML/XML diffing
7. **Docling HTML Export** - Update docling integration to prefer `export_to_html`

**Out of Scope:**
- Visual diff UI, real-time collaboration, version control integration
- Database storage of diffs, authentication/authorization

**Constraints:**
- MUST maintain existing code patterns and architecture
- MUST achieve >80% test coverage for new code
- MUST maintain backward compatibility with existing API
- MUST handle optional dependencies gracefully

## 4. Affected Components

**Files to Modify:**
1. `redlines/redlines.py` - Add JSON output, integrate xmldiff, add red-blue style
2. `redlines/processor.py` - Add xmldiff backend processor, update Redline dataclass
3. `redlines/utils/conversion_manager.py` - Update to use HTML as intermediary
4. `redlines/utils/markdown_processor.py` - Update docling integration
5. `redlines/utils/docx_processor.py` - Add track changes XML generation
6. `redlines/utils/html_processor.py` - Enhance for use as pivot format
7. `redlines/utils/styles.py` - Add red-blue style configuration
8. `pyproject.toml` - Add xmldiff, fastapi, pydantic dependencies

**Files to Create:**
1. `redlines/xmldiff_processor.py` - New processor for xmldiff-based diffing
2. `redlines/api.py` - FastAPI integration with Pydantic models
3. `redlines/models.py` - Pydantic schemas for API and JSON output
4. `redlines/utils/docx_track_changes.py` - DOCX track changes XML generator
5. `tests/test_xmldiff_processor.py` - Tests for xmldiff processor
6. `tests/test_api.py` - Tests for FastAPI integration
7. `tests/test_docx_track_changes.py` - Tests for track changes
8. `tests/test_json_output.py` - Tests for JSON structured output
9. `examples/fastapi_example.py` - Example FastAPI application
10. `examples/xmldiff_example.py` - Example showing xmldiff usage

**Dependencies Affected:**
- **Add**: `xmldiff>=2.7.0`, `lxml>=5.0.0`, `fastapi>=0.115.0`, `pydantic>=2.0.0`
# PRD Part 2: Best Practices, Requirements & Implementation

## 5. Best Practices Research

**Key Findings:**

1. **xmldiff Best Practices** (from xmldiff documentation)
   - Use `text_tags` for block-level content (`p`, `h1`-`h6`, `li`)
   - Use `formatting_tags` for inline formatting (`b`, `i`, `strike`, `span`, `em`)
   - Apply XSLT transforms for visual diff rendering
   - Namespace: `xmlns:diff="http://namespaces.shoobx.com/diff"`

2. **FastAPI Integration Patterns**
   - Use Pydantic V2 models for validation
   - Leverage dependency injection
   - Implement proper error handling with `HTTPException`

3. **DOCX Track Changes** (Office Open XML spec)
   - Insert: `<w:ins w:id="..." w:author="..." w:date="..."><w:r><w:t>text</w:t></w:r></w:ins>`
   - Delete: `<w:del w:id="..." w:author="..." w:date="..."><w:r><w:delText>text</w:delText></w:r></w:del>`

**Anti-patterns to Avoid:**
- Breaking backward compatibility
- Tight coupling to xmldiff
- Synchronous blocking operations
- Hard-coded styles

**Security Considerations:**
1. XML External Entity (XXE) Prevention - Use `lxml` with `resolve_entities=False`
2. API Input Validation - Validate with Pydantic, set max length limits
3. Dependency Security - Pin versions, use security scanning

## 6. Implementation Requirements

### 6.1 Functional Requirements

**REQ-F-001: JSON Structured Output**
- Acceptance Criteria:
  - `Redlines.output_json` property returns structured dict
  - Each diff entry includes: type, indices, content
  - JSON includes metadata: timestamp, version, style
  - `Redlines.to_json_file(path)` method exports to file
- Test Strategy: Unit tests with sample diffs, verify JSON schema

**REQ-F-002: DOCX Track Changes XML**
- Acceptance Criteria:
  - `DOCXProcessor` generates documents with track changes
  - Insertions use `w:ins`, deletions use `w:del` elements
  - Each change has unique ID, author, ISO 8601 timestamp
  - Viewable in Microsoft Word and LibreOffice
- Test Strategy: Generate DOCX, verify XML, manual Word validation

**REQ-F-003: FastAPI Integration**
- Acceptance Criteria:
  - `RedlinesAPI` class with FastAPI router
  - Pydantic models for requests/responses
  - Endpoints: POST /diff, POST /convert, GET /health
  - OpenAPI docs auto-generated
- Test Strategy: TestClient for endpoint testing

**REQ-F-004: Red-Blue Style**
- Acceptance Criteria:
  - `markdown_style='red-blue'` option available
  - Deletions red, insertions blue
  - Works in output_markdown and output_rich
- Test Strategy: Parametrized tests for red-blue

**REQ-F-005: HTML Intermediary Format**
- Acceptance Criteria:
  - `ConversionManager` uses HTML as pivot
  - All conversions: SOURCE → HTML → TARGET
  - Backward compatibility maintained
- Test Strategy: Round-trip conversion tests

**REQ-F-006: xmldiff Integration**
- Acceptance Criteria:
  - `XmlDiffProcessor` implements `RedlinesProcessor`
  - Configured with text_tags/formatting_tags
  - Default when HTML content detected
  - SequenceMatcher fallback for plain text
- Test Strategy: Compare xmldiff vs SequenceMatcher

**REQ-F-007: Docling HTML Export**
- Acceptance Criteria:
  - Try `export_to_html` before `export_to_markdown`
  - Proper HTML conversion to intermediary
  - Maintains formatting fidelity
- Test Strategy: Integration tests with DOCX/PDF

### 6.2 Non-Functional Requirements

- **REQ-NF-001**: Performance - xmldiff ≤2x time of SequenceMatcher for <10KB
- **REQ-NF-002**: Performance - HTML pipeline ≤1.5x time of Markdown
- **REQ-NF-003**: Security - All XML/HTML inputs sanitized
- **REQ-NF-004**: Compatibility - Python 3.10-3.13 support
- **REQ-NF-005**: Maintainability - Follow existing patterns
- **REQ-NF-006**: Documentation - All features documented
- **REQ-NF-007**: Backward Compatibility - All existing tests pass

## 7. Testing Strategy

### 7.1 Test-Driven Development Approach
1. Write failing tests first
2. Implement minimum code to pass
3. Refactor while keeping tests green

### 7.2 Test Coverage Plan

**Unit Tests:**
- `tests/test_json_output.py` (95% coverage) - JSON structure, metadata, file export
- `tests/test_docx_track_changes.py` (90%) - Track changes XML, IDs, timestamps
- `tests/test_xmldiff_processor.py` (95%) - HTML diff, formatter, fallbacks
- `tests/test_api.py` (90%) - Endpoints, validation, error handling
- `tests/test_redline.py` (additions) - Red-blue style, output_json

**Integration Tests:**
- `tests/test_conversion_manager.py` (additions) - HTML round-trips
- `tests/test_docx_processor.py` (additions) - Track changes generation

**E2E Tests:**
- Full API workflow with TestClient
- CLI with JSON output
- DOCX with track changes (manual validation)

### 7.3 Automated Verification
- CI/CD: GitHub Actions on push
- Coverage: pytest-cov with 80% minimum
- Command: `pytest --cov=redlines --cov-report=html`

### 7.4 Manual Verification
1. Open DOCX in Microsoft Word - verify track changes
2. Open DOCX in LibreOffice - verify compatibility
3. Test FastAPI with Swagger UI
4. Compare xmldiff vs SequenceMatcher output
5. Validate JSON with external tool (jq)

## 8. Implementation Plan

### 8.1 Dependencies and Sequencing

1. **Foundation** (MUST complete first) - Update pyproject.toml, create models
2. **xmldiff Integration** - Create processor, integrate with Redlines
3. **JSON Output** - Add properties and methods
4. **DOCX Track Changes** - Create utility, integrate with processor
5. **HTML Intermediary** - Update ConversionManager, docling integration
6. **Red-Blue Style** - Update Styles and output methods
7. **FastAPI Integration** - Create API class and endpoints
8. **Testing & Docs** - Complete test suites, update documentation

### 8.2 File-by-File Implementation

**Phase 1: Test Setup**
- Create all test files with failing tests
- Verify failures
- DO NOT implement yet

**Phase 2: Core Implementation**

1. **pyproject.toml** - Add dependencies (xmldiff, lxml, fastapi, pydantic)
2. **redlines/models.py** (NEW) - Pydantic models for API and JSON
3. **redlines/xmldiff_processor.py** (NEW) - XmlDiffProcessor class
4. **redlines/utils/docx_track_changes.py** (NEW) - Track changes generator
5. **redlines/redlines.py** - Add output_json, xmldiff integration, red-blue
6. **redlines/processor.py** - Update Redline dataclass with to_dict()
7. **redlines/utils/conversion_manager.py** - HTML as intermediary
8. **redlines/utils/markdown_processor.py** - Docling HTML export
9. **redlines/utils/docx_processor.py** - Track changes integration
10. **redlines/utils/styles.py** - Red-blue configuration
11. **redlines/api.py** (NEW) - FastAPI router and endpoints
12. **redlines/__init__.py** - Export new classes

**Phase 3: Integration** - Wire components, run tests, fix issues

**Phase 4: Documentation** - Update README, add examples, update docstrings

### 8.3 Validation Checkpoints
After each phase verify:
- All tests passing
- No new warnings
- Coverage ≥80%
- Manual verification complete

## 9. Risk Assessment

**Technical Risks:**
- xmldiff Performance (High/Medium) - Mitigation: Benchmark, intelligent selection
- DOCX Compatibility (Medium/Medium) - Mitigation: Multi-version testing
- HTML Breaking Changes (High/Low) - Mitigation: Maintain Markdown paths
- Optional Dependencies (Low/Medium) - Mitigation: Import guards, clear errors

**Integration Risks:**
- docling HTML unavailable - Mitigation: Progressive fallbacks
- FastAPI version conflicts - Mitigation: Truly optional, version docs

**Breaking Change Risks:**
- Changing default processor - Mitigation: xmldiff only for HTML content
- JSON schema changes - Mitigation: Extensible design, versioning

## 10. Verification Checklist

- [ ] All functional requirements (REQ-F-001 to REQ-F-007) met
- [ ] All non-functional requirements (REQ-NF-001 to REQ-NF-007) met
- [ ] Test coverage >80% for new code
- [ ] All tests passing
- [ ] No linter errors
- [ ] Manual: DOCX viewable in Word
- [ ] Manual: FastAPI Swagger functional
- [ ] Manual: JSON parseable
- [ ] No broken legacy functionality
- [ ] Documentation updated
- [ ] Code follows patterns
- [ ] Security addressed
- [ ] Performance met
- [ ] Ready to push

## 11. Git Workflow

**Branch Strategy:**
- Branch: `feature/xmldiff-json-api-enhancements`
- Base: main

**Commit Strategy:**
- Conventional commits:
  - `feat(json): add structured JSON output`
  - `feat(docx): implement track changes XML`
  - `feat(api): add FastAPI integration`
  - `feat(xmldiff): integrate xmldiff processor`
  - `feat(html): transition to HTML intermediary`
  - `feat(styles): add red-blue scheme`
  - `test: comprehensive test suite`
  - `docs: update README and examples`
- Atomic commits, tests passing per commit

**Final Steps:**
1. Push feature branch
2. Create PR linking to PRD
3. Code review
4. Address feedback
5. Merge after approval

---

## IMPLEMENTATION COMMITMENT

**I, the AI agent, commit to:**

1. ✅ Implementing this PRD completely and autonomously
2. ✅ Following exact codebase patterns (async, processors, managers)
3. ✅ Writing tests BEFORE implementation (TDD)
4. ✅ Achieving >80% test coverage
5. ✅ Not simplifying unless requested
6. ✅ Not over-engineering
7. ✅ Verifying everything works
8. ✅ Pushing to git when complete
9. ✅ Requiring minimal supervision
10. ✅ Asking clarifying questions only when necessary

---

## NOTES FOR AUTONOMOUS EXECUTION

**Context Management:**
- This PRD is source of truth
- Re-read relevant sections as needed
- Update progress in git commits
- Use verification checklist to track completion

**Decision-Making:**
- Consult codebase patterns first
- Ask user if patterns inconsistent
- Prefer explicit over clever
- Favor maintainability over optimization

**Quality Standards:**
- Pass all existing tests
- Equivalent or better test coverage
- Zero linter warnings
- No performance degradation
