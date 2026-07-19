/**
 * LPTE iOS Native Module (Swift)
 *
 * Bridges the Python LPTE engine to React Native via a native module.
 * The Python engine runs in a background queue to avoid blocking JS.
 *
 * Setup:
 * 1. Add this file to your Xcode project
 * 2. Add RCTBridgeModule.h to your bridging header
 * 3. Run: npx react-native link lpte-react-native
 */

import Foundation
import React

@objc(LpteModule)
class LpteModule: NSObject {

  /// Whether the Python engine is initialized
  private var isInitialized = false

  /// Available language codes
  private var availableLanguages: [String] = ["en", "bn"]

  /// Required: tells React Native this module should NOT run on the main thread
  static func requiresMainQueueSetup() -> Bool {
    return false
  }

  /// Bridge the analyze method to JavaScript
  @objc func analyze(
    _ text: String,
    languageCode: String,
    threshold: Float,
    resolver resolve: @escaping RCTPromiseResolveBlock,
    rejecter reject: @escaping RCTPromiseRejectBlock
  ) {
    // Run on background queue to avoid blocking JS thread
    DispatchQueue.global(qos: .userInitiated).async { [weak self] in
      // In production, this calls the compiled Python engine via:
      // 1. PythonKit (CPython embedding)
      // 2. Chaquopy equivalent for iOS
      // 3. Pre-compiled .xcframework from Kotlin/Native
      //
      // For now, return a placeholder result
      let result: [String: Any] = [
        "isToxic": false,
        "severity": "NONE",
        "confidence": 0.0,
        "matchedTerms": [String]()
      ]

      DispatchQueue.main.async {
        resolve(result)
      }
    }
  }

  /// Bridge the isToxic method to JavaScript
  @objc func isToxic(
    _ text: String,
    languageCode: String,
    threshold: Float,
    resolver resolve: @escaping RCTPromiseResolveBlock,
    rejecter reject: @escaping RCTPromiseRejectBlock
  ) {
    analyze(text, languageCode: languageCode, threshold: threshold) { result in
      if let dict = result as? [String: Any],
         let isToxic = dict["isToxic"] as? Bool {
        resolve(isToxic)
      } else {
        resolve(false)
      }
    } rejecter: { error in
      reject("LpteError", error.localizedDescription, nil)
    }
  }

  /// Bridge the sanitize method to JavaScript
  @objc func sanitize(
    _ text: String,
    languageCode: String,
    mask: String,
    resolver resolve: @escaping RCTPromiseResolveBlock,
    rejecter reject: @escaping RCTPromiseRejectBlock
  ) {
    // Placeholder — in production, calls the engine
    resolve(text)
  }

  /// Bridge loadCustomProfile to JavaScript
  @objc func loadCustomProfile(
    _ assetPath: String,
    languageCode: String,
    resolver resolve: @escaping RCTPromiseResolveBlock,
    rejecter reject: @escaping RCTPromiseRejectBlock
  ) {
    availableLanguages.append(languageCode)
    resolve(nil)
  }
}
