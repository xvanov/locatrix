# Sprint Change Proposal: MVP Acceleration - Epic Reordering and Simplification

**Date:** 2025-01-15  
**Author:** Product Manager (PM Agent)  
**Status:** Draft - Awaiting Approval  
**Change Type:** Major - Epic Reordering and Story Simplification

---

## 1. Issue Summary

### Problem Statement

We are wrapping up Epic 3 (Story 3.2 in review) and facing time pressure to deliver MVP. The core MVP requirement is: **send an image → get back labeled output** (room boundaries). However, the current Epic 3 Story 3.2 is over-engineered for MVP, including multi-stage pipeline orchestration, Step Functions, and WebSocket integration that are not essential for the core MVP functionality.

Additionally, Epic 4 (Caching & Performance) is marked as Growth scope in the PRD, not MVP scope, yet it's currently planned as the next epic. We need to reorder and simplify to reach MVP faster.

### Context

- **Current State:** Epic 3 Story 3.2 (SageMaker Integration) is in review
- **Time Pressure:** Running out of time, need to speed things up
- **Core MVP Need:** Model that can parse blueprints - send image, get labeled output
- **Discovery:** Epic 4 is Growth scope, not MVP scope
- **Request:** Reorder epics from Epic 4 onwards to get basic MVP done ASAP

### Evidence

- PRD Section 6: MVP Scope = Epics 1, 2, 3; Growth Scope = Epics 4, 5
- Epic 3 Story 3.2 includes: multi-stage pipeline, Step Functions orchestration, WebSocket integration
- Core MVP requirement: FR-002 (Process files using AI/ML), FR-003 (Return room coordinates)
- Epic 4 (Caching & Performance) covers FR-010 (Caching support - Growth feature)

---

## 2. Impact Analysis

### Epic Impact

**Epic 3: AI Processing Pipeline**
- **Current Status:** Story 3.1 done, Story 3.2 in review
- **Impact:** Story 3.2 is over-scoped for MVP
- **Required Changes:** Simplify Story 3.2 to focus on core MVP: image → labeled output
- **Defer:** Multi-stage pipeline, Step Functions orchestration, WebSocket integration

**Epic 4: Caching & Performance**
- **Current Status:** Backlog
- **Impact:** Not required for MVP (Growth scope)
- **Required Changes:** Defer to post-MVP
- **Rationale:** Caching is optimization, not core functionality

**Epic 5: Frontend Integration**
- **Current Status:** Backlog
- **Impact:** Not required for MVP (Growth scope)
- **Required Changes:** Defer to post-MVP
- **Rationale:** MVP can be tested via API; frontend is Growth feature

**Epic 6: Testing & Deployment**
- **Current Status:** Backlog
- **Impact:** Not required for MVP (Vision scope)
- **Required Changes:** Defer to post-MVP
- **Rationale:** Basic testing can be done during development; comprehensive testing is post-MVP

### Story Impact

**Epic 3 Story 3.2: SageMaker Integration with Complete Processing Pipeline**
- **Current Scope:** Multi-stage pipeline with Step Functions orchestration
- **MVP Need:** Direct SageMaker model invocation - image → labeled output
- **Required Simplification:** Remove multi-stage orchestration, focus on core model integration

### Artifact Conflicts

**PRD:**
- No conflicts - PRD correctly identifies MVP scope as Epics 1, 2, 3
- Need to clarify that Epic 3 should be simplified for MVP

**Architecture:**
- Current design includes multi-stage pipeline with Step Functions
- MVP can use simpler direct model invocation
- Architecture can be enhanced post-MVP

**Epics Document:**
- Epic 3 Story 3.2 needs simplification
- Epic 4-6 need to be marked as deferred to post-MVP

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment + Epic Reordering

**Rationale:**
1. **Simplifies Epic 3 Story 3.2** to focus on MVP essentials (image → labeled output)
2. **Maintains Epic 3 structure** while removing non-MVP complexity
3. **Defers Epic 4-6** to post-MVP (they're Growth/Vision scope anyway)
4. **Fastest path to MVP** - removes unnecessary complexity

**Effort Estimate:** Medium  
**Risk Level:** Low  
**Timeline Impact:** Faster to MVP

### Implementation Strategy

1. **Simplify Epic 3 Story 3.2:**
   - Keep: SageMaker model invocation, input preprocessing, output post-processing
   - Remove: Multi-stage pipeline orchestration, Step Functions, WebSocket integration
   - Focus: Direct model invocation - image → labeled output

2. **Reorder Epics 4-6:**
   - Epic 4: Defer to post-MVP (Growth scope)
   - Epic 5: Defer to post-MVP (Growth scope)
   - Epic 6: Defer to post-MVP (Vision scope)

3. **Update Documentation:**
   - Update epics.md to reflect simplified Story 3.2
   - Update PRD to clarify MVP scope
   - Update sprint-status.yaml to reflect new priorities

---

## 4. Detailed Change Proposals

### Change Proposal 1: Simplify Epic 3 Story 3.2

**Story:** Epic 3 Story 3.2 - SageMaker Integration with Complete Processing Pipeline

**Section:** Story Goal

**OLD:**
```
As a developer,
I want to integrate SageMaker and deploy a complete multi-stage processing pipeline with Step Functions orchestration,
So that users can see progressively improved results with a testable, end-to-end workflow.
```

**NEW:**
```
As a developer,
I want to integrate SageMaker and deploy a direct model invocation pipeline,
So that users can send a blueprint image and receive labeled room boundaries with a testable, end-to-end workflow.
```

**Section:** Acceptance Criteria

**OLD:**
- Multi-stage workflow: preview → intermediate → final
- Step Functions orchestration
- `src/pipeline/stage_2_intermediate.py` Lambda handler
- `src/pipeline/stage_3_final.py` Lambda handler
- `src/pipeline/step_functions.py` with state machine definition
- Three-stage workflow: preview → intermediate → final
- WebSocket integration for real-time progress updates
- Intermediate and final results stored in S3 and DynamoDB

**NEW:**
- Direct SageMaker model invocation for room detection
- `src/services/sagemaker_service.py` with SageMaker client integration
- Model endpoint invocation for room detection
- Input preprocessing: blueprint image → model format
- Output post-processing: model response → labeled room boundaries
- `src/pipeline/process_blueprint.py` Lambda handler (single-stage)
- Results stored in DynamoDB and S3
- REST API endpoint to retrieve results
- Return labeled output (room boundaries with bounding boxes)

**Deferred to Post-MVP:**
- Multi-stage pipeline orchestration
- Step Functions state machine
- WebSocket integration for real-time progress updates
- Intermediate processing stages

**Rationale:**
- MVP requirement: send image → get labeled output
- Multi-stage pipeline and Step Functions are optimization (can be added post-MVP)
- WebSocket is Growth feature (FR-009)
- Simplifying to core MVP functionality accelerates delivery

---

### Change Proposal 2: Reorder Epics 4-6

**Epic 4: Caching & Performance**
- **Status:** Defer to post-MVP (Growth scope)
- **Rationale:** Not required for MVP; optimization can come later
- **Action:** Move to backlog, mark as post-MVP

**Epic 5: Frontend Integration**
- **Status:** Defer to post-MVP (Growth scope)
- **Rationale:** MVP can be tested via API; frontend is Growth feature
- **Action:** Move to backlog, mark as post-MVP

**Epic 6: Testing & Deployment**
- **Status:** Defer to post-MVP (Vision scope)
- **Rationale:** Basic testing can be done during development; comprehensive testing is post-MVP
- **Action:** Move to backlog, mark as post-MVP

---

### Change Proposal 3: Update PRD Epic Scope Mapping

**Section:** Epic Breakdown (Section 6)

**Current:**
- **MVP Scope:** Epics 1, 2, 3 (core functionality)
- **Growth Scope:** Epics 4, 5 (optimization and integration)
- **Vision Scope:** Epic 6 (comprehensive testing and deployment)

**Updated:**
- **MVP Scope:** Epics 1, 2, 3 (core functionality) - Epic 3 simplified to focus on core model integration
- **Growth Scope:** Epics 4, 5 (optimization and integration) - Deferred to post-MVP
- **Vision Scope:** Epic 6 (comprehensive testing and deployment) - Deferred to post-MVP

**Rationale:**
- Clarifies MVP scope and aligns with time pressure
- Confirms Epic 4-6 are not required for MVP

---

## 5. Implementation Handoff

### Change Scope Classification: **Major**

This change requires fundamental replanning with PM/Architect involvement.

### Handoff Recipients

**Product Manager (PM):**
- Review and approve simplified Epic 3 Story 3.2
- Update PRD Epic Scope Mapping
- Coordinate with Architect on simplified architecture

**Solution Architect:**
- Review simplified architecture approach (direct model invocation vs. multi-stage pipeline)
- Validate that simplified approach meets MVP requirements
- Plan for post-MVP enhancements (multi-stage pipeline, Step Functions)

**Scrum Master:**
- Update sprint-status.yaml to reflect new priorities
- Reorganize backlog: Epic 4-6 moved to post-MVP
- Update Epic 3 Story 3.2 with simplified acceptance criteria

**Development Team:**
- Implement simplified Epic 3 Story 3.2
- Focus on core MVP: image → labeled output
- Defer multi-stage pipeline and Step Functions to post-MVP

### Success Criteria

1. **Epic 3 Story 3.2 Simplified:**
   - Direct SageMaker model invocation implemented
   - Image → labeled output workflow working
   - Results returned via REST API
   - Processing time under 30 seconds

2. **Epics 4-6 Deferred:**
   - Epic 4-6 moved to backlog
   - Marked as post-MVP
   - No work started on Epic 4-6

3. **Documentation Updated:**
   - epics.md updated with simplified Story 3.2
   - PRD updated with clarified MVP scope
   - sprint-status.yaml updated with new priorities

---

## 6. Next Steps

1. **Immediate Actions:**
   - Review and approve this Sprint Change Proposal
   - Update Epic 3 Story 3.2 with simplified acceptance criteria
   - Update sprint-status.yaml to reflect new priorities

2. **Short-term Actions:**
   - Architect reviews simplified architecture approach
   - Development team implements simplified Story 3.2
   - Test image → labeled output workflow

3. **Post-MVP Actions:**
   - Plan Epic 4-6 for post-MVP delivery
   - Enhance Epic 3 with multi-stage pipeline (if needed)
   - Add Step Functions orchestration (if needed)

---

## 7. Risks and Mitigation

**Risk 1: Simplified approach may not meet performance requirements**
- **Mitigation:** Monitor processing time; add optimizations if needed
- **Contingency:** Can add caching (Epic 4) if performance is an issue

**Risk 2: Post-MVP enhancements may require significant refactoring**
- **Mitigation:** Design simplified approach with extensibility in mind
- **Contingency:** Architecture can be enhanced incrementally

**Risk 3: Stakeholder expectations may not align with simplified MVP**
- **Mitigation:** Communicate MVP scope clearly; set expectations
- **Contingency:** Can prioritize specific Growth features if needed

---

**Document Status:** Awaiting Approval

**Approval Required From:**
- Product Manager
- Solution Architect
- Scrum Master

---

_This Sprint Change Proposal is generated as part of the Correct Course workflow to navigate significant changes during sprint execution._

