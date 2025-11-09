/**
 * Data factories for Story 3.1: Textract Service Integration with Preview Pipeline
 * Uses faker for dynamic test data generation
 */

import { faker } from '@faker-js/faker';

export interface Job {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  stage?: 'stage_1' | 'stage_2' | 'stage_3';
  blueprint_s3_key?: string;
  created_at: string;
  updated_at: string;
}

export interface Room {
  id: string;
  bounding_box: [number, number, number, number]; // [x_min, y_min, x_max, y_max]
  name_hint?: string;
  confidence: number;
}

export interface PreviewResult {
  job_id: string;
  stage: 'preview';
  rooms: Room[];
  processing_time_seconds: number;
  timestamp: string;
}

export interface TextractAnalysisResult {
  job_id: string;
  text_blocks: Array<{
    id: string;
    text: string;
    geometry: {
      boundingBox: {
        left: number;
        top: number;
        width: number;
        height: number;
      };
    };
  }>;
  layout_blocks: Array<{
    id: string;
    blockType: string;
    geometry: {
      boundingBox: {
        left: number;
        top: number;
        width: number;
        height: number;
      };
    };
  }>;
  metadata: {
    pages: number;
    analyzed_at: string;
  };
}

/**
 * Create a job with optional overrides
 */
export const createJob = (overrides: Partial<Job> = {}): Job => ({
  job_id: `job_${faker.date.recent().toISOString().replace(/[-:]/g, '').split('.')[0]}_${faker.string.alphanumeric(6)}`,
  status: 'pending',
  created_at: faker.date.recent().toISOString(),
  updated_at: faker.date.recent().toISOString(),
  ...overrides,
});

/**
 * Create multiple jobs
 */
export const createJobs = (count: number, overrides: Partial<Job> = {}): Job[] =>
  Array.from({ length: count }, () => createJob(overrides));

/**
 * Create a room detection result with optional overrides
 */
export const createRoom = (overrides: Partial<Room> = {}): Room => ({
  id: `room_${faker.string.numeric(3).padStart(3, '0')}`,
  bounding_box: [
    faker.number.int({ min: 0, max: 100 }),
    faker.number.int({ min: 0, max: 100 }),
    faker.number.int({ min: 200, max: 500 }),
    faker.number.int({ min: 200, max: 500 }),
  ] as [number, number, number, number],
  name_hint: faker.location.room(),
  confidence: faker.number.float({ min: 0.5, max: 1.0, fractionDigits: 2 }),
  ...overrides,
});

/**
 * Create multiple rooms
 */
export const createRooms = (count: number, overrides: Partial<Room> = {}): Room[] =>
  Array.from({ length: count }, () => createRoom(overrides));

/**
 * Create a preview result with optional overrides
 */
export const createPreviewResult = (overrides: Partial<PreviewResult> = {}): PreviewResult => ({
  job_id: createJob().job_id,
  stage: 'preview',
  rooms: createRooms(faker.number.int({ min: 1, max: 10 })),
  processing_time_seconds: faker.number.float({ min: 0.5, max: 5.0, fractionDigits: 2 }),
  timestamp: new Date().toISOString(),
  ...overrides,
});

/**
 * Create a Textract analysis result with optional overrides
 */
export const createTextractAnalysisResult = (overrides: Partial<TextractAnalysisResult> = {}): TextractAnalysisResult => {
  const jobId = createJob().job_id;
  return {
    job_id: jobId,
    text_blocks: Array.from({ length: faker.number.int({ min: 5, max: 20 }) }, (_, i) => ({
      id: `text_${i}`,
      text: faker.lorem.words(3),
      geometry: {
        boundingBox: {
          left: faker.number.float({ min: 0, max: 100 }),
          top: faker.number.float({ min: 0, max: 100 }),
          width: faker.number.float({ min: 50, max: 200 }),
          height: faker.number.float({ min: 20, max: 100 }),
        },
      },
    })),
    layout_blocks: Array.from({ length: faker.number.int({ min: 3, max: 15 }) }, (_, i) => ({
      id: `layout_${i}`,
      blockType: faker.helpers.arrayElement(['PAGE', 'LINE', 'WORD', 'TABLE', 'CELL']),
      geometry: {
        boundingBox: {
          left: faker.number.float({ min: 0, max: 100 }),
          top: faker.number.float({ min: 0, max: 100 }),
          width: faker.number.float({ min: 50, max: 200 }),
          height: faker.number.float({ min: 20, max: 100 }),
        },
      },
    })),
    metadata: {
      pages: faker.number.int({ min: 1, max: 5 }),
      analyzed_at: new Date().toISOString(),
    },
    ...overrides,
  };
};


