/**
 * Helper to load real blueprint images from fixtures directory
 */

import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Load a blueprint image from the fixtures directory and return as base64
 * @param filename - Name of the blueprint file (e.g., 'sample-floor-plan.jpg')
 * @returns Base64-encoded string of the image
 */
export function loadBlueprintFromFixtures(filename: string): string {
  const blueprintPath = join(__dirname, '../fixtures/blueprints', filename);
  const blueprintData = readFileSync(blueprintPath);
  return blueprintData.toString('base64');
}

/**
 * Available blueprint fixtures
 */
export const BLUEPRINT_FIXTURES = {
  sampleFloorPlan: 'sample-floor-plan.jpg', // Add your real blueprint here
} as const;


