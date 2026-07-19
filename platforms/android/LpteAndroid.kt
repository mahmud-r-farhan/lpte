package dev.lpte.platforms.android

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Android wrapper for the LPTE toxicity engine.
 *
 * In production, this calls the Python core via:
 * 1. Chaquopy (Python-in-Android plugin)
 * 2. Or a gRPC/local server running the Python engine
 *
 * For now, this provides the API surface and JSON-based
 * language pack loading from Android assets.
 */
object LpteAndroid {

    private const val TAG = "LPTE"
    private val loadedProfiles = mutableMapOf<String, JSONObject>()

    /**
     * Load a language profile from an Android asset JSON file.
     *
     * @param context Android context
     * @param assetPath Path to JSON file in assets/ directory
     * @param languageCode Language code to register under
     */
    fun loadProfile(context: Context, assetPath: String, languageCode: String) {
        try {
            val json = context.assets.open(assetPath).bufferedReader().use { it.readText() }
            loadedProfiles[languageCode] = JSONObject(json)
            Log.i(TAG, "Loaded profile for $languageCode from $assetPath")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load profile: ${e.message}", e)
        }
    }

    /**
     * Check if a profile is loaded for the given language.
     */
    fun hasProfile(languageCode: String): Boolean {
        return loadedProfiles.containsKey(languageCode)
    }

    /**
     * Get available language codes.
     */
    fun availableLanguages(): List<String> {
        return loadedProfiles.keys.toList()
    }

    // NOTE: The actual analyze/isToxic/sanitize methods would call
    // the Python engine via Chaquopy or a local server.
    // This is the API surface that the Android app would use.
}
