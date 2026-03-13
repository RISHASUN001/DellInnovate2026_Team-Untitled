/**
 * OpenAI Integration Module
 * Handles all communication with OpenAI API for content analysis
 */

const OPENAI_API_URL = "https://api.openai.com/v1/chat/completions";
const MODEL = "gpt-4o"; // Latest GPT-4 with vision capabilities
const ANALYSIS_MODEL = "gpt-4o"; // For text-only analysis

/**
 * Main function to analyze Instagram content using OpenAI
 * @param {string} screenshotBase64 - Base64 encoded screenshot
 * @param {object} extractedContent - Extracted text content from Instagram
 * @param {string} apiKey - OpenAI API key
 * @param {string} orgId - Optional OpenAI Organization ID
 * @returns {Promise<object>} Analysis results
 */
async function analyzeWithOpenAI(
  screenshotBase64,
  extractedContent,
  apiKey,
  orgId,
) {
  try {
    // Prepare content for analysis
    const analysisPrompt = buildAnalysisPrompt(extractedContent);

    // Build the request payload
    const payload = {
      model: MODEL,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "text",
              text: analysisPrompt,
            },
            {
              type: "image_url",
              image_url: {
                url: screenshotBase64,
                detail: "high",
              },
            },
          ],
        },
      ],
      max_tokens: 1000,
      temperature: 0.3, // Lower temperature for consistent analysis
    };

    // Make API request
    const response = await fetchOpenAI(payload, apiKey, orgId);

    // Parse response
    const analysisText = response.choices[0].message.content;
    const analysis = parseAnalysisResponse(analysisText);

    return analysis;
  } catch (error) {
    console.error("OpenAI analysis error:", error);
    throw new Error(`Analysis failed: ${error.message}`);
  }
}

/**
 * Build the prompt for OpenAI analysis
 * @param {object} extractedContent - Extracted content from page
 * @returns {string} Formatted prompt
 */
function buildAnalysisPrompt(extractedContent) {
  const textContent = formatExtractedContent(extractedContent);

  return `You are assisting youth outreach workers in identifying potential mental health risk signals on Instagram profiles.

IMPORTANT: You are NOT diagnosing mental health conditions. You are ONLY identifying potential concerning signals that warrants further attention by trained professionals.

Analyze the Instagram profile content shown in the screenshot and the extracted text below.

EXTRACTED TEXT CONTENT:
${textContent}

Your task: Identify signals that may indicate distress, social isolation, bullying, self-harm risk, substance use, or other mental health concerns.

Focus on analyzing:
- Captions expressing sadness, hopelessness, loneliness, or despair
- Language indicating self-harm, suicidal ideation, or substance use
- Harmful or abusive comments from others
- Imagery suggesting distress, self-harm, weapons, drugs, or violence
- Repeated negative emotional patterns
- Signals of isolation or withdrawal
- Evidence of harassment or bullying

RESPOND ONLY with valid JSON in this exact format (no markdown, no code blocks):
{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "signals_detected": ["signal1", "signal2"],
  "flagged_comments": ["comment1", "comment2"],
  "summary": "Brief 1-2 sentence explanation of findings"
}

Risk Levels:
- LOW: No concerning signals detected
- MEDIUM: Some signals present but not immediately alarming
- HIGH: Multiple concerning signals requiring attention
- CRITICAL: Severe signals suggesting immediate risk (self-harm, suicide, violence)

Be objective and specific. Only flag actual concerning language/imagery, not normal teenage expression.`;
}

/**
 * Format extracted content into readable text for the prompt
 * @param {object} content - Extracted Instagram content
 * @returns {string} Formatted text
 */
function formatExtractedContent(content) {
  let formatted = "";

  if (content.profileBio) {
    formatted += `PROFILE BIO:\n${content.profileBio}\n\n`;
  }

  if (content.posts && content.posts.length > 0) {
    formatted += "RECENT POSTS:\n";
    content.posts.forEach((post, index) => {
      formatted += `\nPost ${index + 1}:\n`;
      if (post.caption) {
        formatted += `Caption: ${post.caption}\n`;
      }
      if (post.altTexts && post.altTexts.length > 0) {
        formatted += `Image descriptions: ${post.altTexts.join(", ")}\n`;
      }
      if (post.links && post.links.length > 0) {
        formatted += `Tags/Mentions: ${post.links.join(", ")}\n`;
      }
    });
    formatted += "\n";
  }

  if (content.visibleComments && content.visibleComments.length > 0) {
    formatted += "VISIBLE COMMENTS:\n";
    content.visibleComments.slice(0, 30).forEach((comment, index) => {
      formatted += `- ${comment}\n`;
    });
    formatted += "\n";
  }

  return formatted || "No extractable content found on page.";
}

/**
 * Make HTTP request to OpenAI API
 * @param {object} payload - Request payload
 * @param {string} apiKey - OpenAI API key
 * @param {string} orgId - Optional Organization ID
 * @returns {Promise<object>} API response
 */
async function fetchOpenAI(payload, apiKey, orgId) {
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${apiKey}`,
  };

  // Add Organization ID if provided
  if (orgId && orgId.trim()) {
    headers["OpenAI-Organization"] = orgId;
  }

  const response = await fetch(OPENAI_API_URL, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(
      `OpenAI API error: ${error.error?.message || response.statusText}`,
    );
  }

  return await response.json();
}

/**
 * Parse the analysis response from OpenAI
 * @param {string} responseText - Raw response from OpenAI
 * @returns {object} Parsed analysis
 */
function parseAnalysisResponse(responseText) {
  try {
    // Extract JSON from response (handle various formats)
    let jsonString = responseText.trim();

    // Remove markdown code blocks if present
    if (jsonString.includes("```")) {
      jsonString = jsonString
        .replace(/```json\n?/g, "")
        .replace(/```\n?/g, "")
        .trim();
    }

    // Find JSON object
    const jsonMatch = jsonString.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error("No JSON found in response");
    }

    const analysis = JSON.parse(jsonMatch[0]);

    // Validate response structure
    if (!analysis.risk_level) {
      throw new Error("Missing risk_level in response");
    }

    // Ensure arrays are present
    if (!Array.isArray(analysis.signals_detected)) {
      analysis.signals_detected = [];
    }
    if (!Array.isArray(analysis.flagged_comments)) {
      analysis.flagged_comments = [];
    }

    // Normalize risk level
    analysis.risk_level = analysis.risk_level.toUpperCase();

    return analysis;
  } catch (error) {
    console.error(
      "Failed to parse OpenAI response:",
      error,
      "Response:",
      responseText,
    );
    // Return safe default response
    return {
      risk_level: "UNKNOWN",
      signals_detected: ["Unable to parse analysis"],
      flagged_comments: [],
      summary: "Error processing response. Please check API key and try again.",
    };
  }
}

console.log("OpenAI module loaded");
