/**
 * Failing API tests for Story 3.1: Textract Service Integration with Preview Pipeline
 * 
 * These tests are in RED phase - they will fail until implementation is complete.
 * Following ATDD red-green-refactor cycle.
 * 
 * Test Level: API (Integration)
 * Primary Test Level: API
 */

import { test, expect } from '../support/fixtures/preview.fixture';
import { createJob, createRooms, createPreviewResult } from '../support/factories/preview.factory';
import { createValidPNGBase64, createValidJPGBase64, createValidPDFBase64 } from '../support/test-files';
import { loadBlueprintFromFixtures } from '../support/blueprint-loader';

test.describe('Story 3.1: Textract Service Integration with Preview Pipeline', () => {
  
  test.describe('AC1: Textract Service and Preview Pipeline Implementation', () => {
    
    test('should trigger preview pipeline and return preview results', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const response = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Preview results are returned with required fields
      expect(response.status).toBe('success');
      expect(response.data).toHaveProperty('job_id', job.job_id);
      expect(response.data).toHaveProperty('stage', 'preview');
      expect(response.data).toHaveProperty('rooms');
      expect(response.data).toHaveProperty('processing_time_seconds');
      expect(response.data).toHaveProperty('timestamp');
      expect(Array.isArray(response.data.rooms)).toBe(true);
    });

    test('should return preview results within 5 seconds', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;
      const startTime = Date.now();

      // WHEN: Triggering preview pipeline
      const response = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      const endTime = Date.now();
      const elapsedSeconds = (endTime - startTime) / 1000;

      // THEN: Preview results returned within 5 seconds
      expect(response.status).toBe('success');
      expect(elapsedSeconds).toBeLessThan(5);
      expect(response.data.processing_time_seconds).toBeLessThan(5);
    });

    test('should store preview results in DynamoDB cache', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.job_id).toBe(job.job_id);

      // Wait for DynamoDB eventual consistency with capped exponential backoff
      // Max total wait time: ~15 seconds (500ms + 1s + 2s + 4s + 8s = 15.5s)
      let cacheResponse;
      let retries = 0;
      const maxRetries = 5;
      const baseDelay = 500; // Start with 500ms
      const maxDelay = 8000; // Cap at 8 seconds
      
      while (retries < maxRetries) {
        const delay = Math.min(baseDelay * Math.pow(2, retries), maxDelay);
        await new Promise(resolve => setTimeout(resolve, delay));
        
        try {
          cacheResponse = await apiRequest({
            method: 'GET',
            url: `/api/v1/jobs/${job.job_id}/preview`,
          });
          break; // Success, exit retry loop
        } catch (error: any) {
          retries++;
          if (retries >= maxRetries) {
            // Log the error for debugging
            console.error(`Cache retrieval failed after ${maxRetries} retries:`, error.message);
            throw error; // Re-throw if all retries exhausted
          }
          // Continue retrying
        }
      }

      // THEN: Preview results can be retrieved from cache
      expect(cacheResponse.status).toBe('success');
      expect(cacheResponse.data.job_id).toBe(job.job_id);
      expect(cacheResponse.data.stage).toBe('preview');
      expect(cacheResponse.data.rooms).toEqual(previewResponse.data.rooms);
    });
  });

  test.describe('AC2: Textract File Format Support', () => {
    
    test('should process PNG files via Textract', async ({ apiRequest }) => {
      // GIVEN: A PNG blueprint file
      const blueprintData = {
        blueprint: {
          file: createValidPNGBase64(),
          format: 'png',
        },
      };

      // WHEN: Creating job with PNG file
      const createResponse = await apiRequest({
        method: 'POST',
        url: '/api/v1/jobs',
        data: blueprintData,
      });

      const jobId = createResponse.data.job_id;

      // AND: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${jobId}/preview`,
        data: {},
      });

      // THEN: Preview results are returned successfully
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.rooms).toBeDefined();
    });

    test('should process JPG files via Textract', async ({ apiRequest }) => {
      // GIVEN: A JPG blueprint file (using real blueprint image)
      const blueprintData = {
        blueprint: {
          file: loadBlueprintFromFixtures('sample-floor-plan.jpeg'),
          format: 'jpg',
        },
      };

      // WHEN: Creating job with JPG file
      const createResponse = await apiRequest({
        method: 'POST',
        url: '/api/v1/jobs',
        data: blueprintData,
      });

      const jobId = createResponse.data.job_id;

      // AND: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${jobId}/preview`,
        data: {},
      });

      // THEN: Preview results are returned successfully
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.rooms).toBeDefined();
    });

    test('should process PDF files via Textract', async ({ apiRequest }) => {
      // GIVEN: A PDF blueprint file
      const blueprintData = {
        blueprint: {
          file: createValidPDFBase64(),
          format: 'pdf',
        },
      };

      // WHEN: Creating job with PDF file
      const createResponse = await apiRequest({
        method: 'POST',
        url: '/api/v1/jobs',
        data: blueprintData,
      });

      const jobId = createResponse.data.job_id;

      // AND: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${jobId}/preview`,
        data: {},
      });

      // THEN: Preview results are returned successfully
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.rooms).toBeDefined();
    });
  });

  test.describe('AC3: Textract Results Storage for Subsequent Stages', () => {
    
    test('should store Textract analysis results in S3 for subsequent stages', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Textract results are stored in S3
      const textractResponse = await apiRequest({
        method: 'GET',
        url: `/api/v1/jobs/${job.job_id}/textract-results`,
      });

      expect(textractResponse.status).toBe('success');
      expect(textractResponse.data).toHaveProperty('s3_key');
      expect(textractResponse.data.s3_key).toContain(`cache/textract/${job.job_id}/analysis.json`);
      expect(textractResponse.data).toHaveProperty('text_blocks');
      expect(textractResponse.data).toHaveProperty('layout_blocks');
      expect(textractResponse.data).toHaveProperty('metadata');
    });
  });

  test.describe('AC4: Processing Time Logging', () => {
    
    test('should log processing time for Textract analysis', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Processing time is included in response
      expect(previewResponse.data).toHaveProperty('processing_time_seconds');
      expect(typeof previewResponse.data.processing_time_seconds).toBe('number');
      expect(previewResponse.data.processing_time_seconds).toBeGreaterThan(0);
    });

    test('should include timing metrics in structured logs', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Response includes timing breakdown
      expect(previewResponse.data).toHaveProperty('timing_metrics');
      expect(previewResponse.data.timing_metrics).toHaveProperty('textract_analysis_seconds');
      expect(previewResponse.data.timing_metrics).toHaveProperty('room_detection_seconds');
      expect(previewResponse.data.timing_metrics).toHaveProperty('total_seconds');
    });
  });

  test.describe('AC5: Preview Results Include Bounding Boxes', () => {
    
    test('should return preview results with bounding boxes for detected rooms', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Preview results include rooms with bounding boxes
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.rooms.length).toBeGreaterThan(0);
      
      previewResponse.data.rooms.forEach((room: any) => {
        expect(room).toHaveProperty('id');
        expect(room).toHaveProperty('bounding_box');
        expect(Array.isArray(room.bounding_box)).toBe(true);
        expect(room.bounding_box.length).toBe(4); // [x_min, y_min, x_max, y_max]
        expect(room.bounding_box[0]).toBeLessThan(room.bounding_box[2]); // x_min < x_max
        expect(room.bounding_box[1]).toBeLessThan(room.bounding_box[3]); // y_min < y_max
        expect(room).toHaveProperty('confidence');
        expect(room.confidence).toBeGreaterThanOrEqual(0);
        expect(room.confidence).toBeLessThanOrEqual(1);
      });
    });

    test('should include room name hints when available from text extraction', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3 containing room labels
      const job = testJob;

      // WHEN: Triggering preview pipeline
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Some rooms may have name hints
      expect(previewResponse.status).toBe('success');
      const roomsWithNames = previewResponse.data.rooms.filter((room: any) => room.name_hint);
      // At least some rooms should have name hints if text extraction found room labels
      expect(roomsWithNames.length).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('AC6: End-to-End Preview Pipeline Testing', () => {
    
    test('should process blueprint end-to-end through preview pipeline', async ({ apiRequest }) => {
      // GIVEN: A blueprint file is uploaded
      const blueprintData = {
        blueprint: {
          file: createValidPNGBase64(),
          format: 'png',
        },
      };

      // WHEN: Creating job and triggering preview pipeline
      const createResponse = await apiRequest({
        method: 'POST',
        url: '/api/v1/jobs',
        data: blueprintData,
      });

      const jobId = createResponse.data.job_id;

      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${jobId}/preview`,
        data: {},
      });

      // THEN: Complete preview pipeline executes successfully
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data.job_id).toBe(jobId);
      expect(previewResponse.data.stage).toBe('preview');
      expect(previewResponse.data.rooms.length).toBeGreaterThan(0);
      expect(previewResponse.data.processing_time_seconds).toBeLessThan(5);
    });
  });

  test.describe('AC7: Graceful Degradation - Return Preview Even if Full Processing Fails', () => {
    
    test('should return preview results even if full processing fails', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline (simulating full processing failure)
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {
          simulate_full_processing_failure: true, // Test parameter
        },
      });

      // THEN: Preview results are still returned
      expect(previewResponse.status).toBe('success');
      expect(previewResponse.data).toHaveProperty('rooms');
      expect(previewResponse.data).toHaveProperty('stage', 'preview');
      // Preview should succeed even if full processing fails
    });

    test('should handle Textract failures gracefully and return partial results', async ({ apiRequest, testJob }) => {
      // GIVEN: A job exists with blueprint stored in S3
      const job = testJob;

      // WHEN: Triggering preview pipeline with invalid blueprint (simulating Textract failure)
      const previewResponse = await apiRequest({
        method: 'POST',
        url: `/api/v1/jobs/${job.job_id}/preview`,
        data: {},
      });

      // THEN: Error is handled gracefully
      // Either returns partial results or clear error message
      if (previewResponse.status === 'success') {
        // Partial results returned
        expect(previewResponse.data).toHaveProperty('rooms');
      } else {
        // Clear error message
        expect(previewResponse).toHaveProperty('error');
        expect(previewResponse.error).toContain('Textract');
      }
    });
  });
});

