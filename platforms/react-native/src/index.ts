/**
 * LPTE React Native Bridge
 *
 * Communicates with the Python LPTE engine via a native module.
 * The native side runs the Python engine in a background thread
 * and returns results via promises.
 */

import { NativeModules } from 'react-native';

const { LpteModule } = NativeModules;

export interface LpteResult {
  isToxic: boolean;
  severity: 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  matchedTerms: string[];
}

export interface LpteOptions {
  languageCode?: string;
  threshold?: number;
}

/**
 * Analyze text for toxic content.
 *
 * @param text - Input text to analyze
 * @param options - Analysis options (language, threshold)
 * @returns Promise resolving to classification result
 */
export async function analyze(
  text: string,
  options: LpteOptions = {}
): Promise<LpteResult> {
  const { languageCode = 'en', threshold = 0.6 } = options;

  if (!LpteModule) {
    throw new Error(
      'LPTE native module not linked. Run: npx react-native link lpte-react-native'
    );
  }

  return LpteModule.analyze(text, languageCode, threshold);
}

/**
 * Quick toxicity check — returns true if text is toxic.
 *
 * @param text - Input text
 * @param options - Analysis options
 * @returns Promise<boolean>
 */
export async function isToxic(
  text: string,
  options: LpteOptions = {}
): Promise<boolean> {
  const result = await analyze(text, options);
  return result.isToxic;
}

/**
 * Sanitize text by masking toxic segments.
 *
 * @param text - Input text
 * @param languageCode - Language code
 * @param mask - Mask character (default '*')
 * @returns Promise<string>
 */
export async function sanitize(
  text: string,
  languageCode: string = 'en',
  mask: string = '*'
): Promise<string> {
  if (!LpteModule) {
    throw new Error('LPTE native module not linked.');
  }

  return LpteModule.sanitize(text, languageCode, mask);
}

/**
 * Load a custom language profile from a JSON asset.
 *
 * @param assetPath - Path to JSON file in assets
 * @param languageCode - Language code to register
 */
export async function loadCustomProfile(
  assetPath: string,
  languageCode: string
): Promise<void> {
  if (!LpteModule) {
    throw new Error('LPTE native module not linked.');
  }

  return LpteModule.loadCustomProfile(assetPath, languageCode);
}

export default { analyze, isToxic, sanitize, loadCustomProfile };
