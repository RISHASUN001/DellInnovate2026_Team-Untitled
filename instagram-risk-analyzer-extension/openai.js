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
    console.log("=== analyzeWithOpenAI started ===");
    console.log("Screenshot Base64 length:", screenshotBase64?.length || 0);
    console.log(
      "Screenshot starts with:",
      screenshotBase64?.substring(0, 50) || "MISSING",
    );
    console.log("Extracted content keys:", Object.keys(extractedContent || {}));
    if (extractedContent?.posts) {
      console.log("Number of posts:", extractedContent.posts.length);
    }
    if (extractedContent?.visibleComments) {
      console.log(
        "Number of comments:",
        extractedContent.visibleComments.length,
      );
    }

    // Prepare content for analysis
    const analysisPrompt = buildAnalysisPrompt(extractedContent);
    console.log("Prompt built, length:", analysisPrompt.length);

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

    console.log("Payload prepared, calling fetchOpenAI...");

    // Make API request
    const response = await fetchOpenAI(payload, apiKey, orgId);

    console.log("Got response from fetchOpenAI");
    console.log("Response structure:", {
      hasChoices: !!response.choices,
      choicesLength: response.choices?.length,
      hasMessage: !!response.choices?.[0]?.message,
      hasContent: !!response.choices?.[0]?.message?.content,
      contentType: typeof response.choices?.[0]?.message?.content,
    });

    // Parse response
    const analysisText = response.choices[0].message.content;
    console.log("Extracted analysis text, length:", analysisText?.length || 0);

    const analysis = parseAnalysisResponse(analysisText);
    console.log("=== analyzeWithOpenAI complete ===");

    return analysis;
  } catch (error) {
    console.error("=== analyzeWithOpenAI ERROR ===");
    console.error("Error type:", error.constructor.name);
    console.error("Error message:", error.message);
    console.error("Error stack:", error.stack);
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

  console.log("Sending request to OpenAI API...");
  console.log("Payload model:", payload.model);
  console.log("Number of messages:", payload.messages.length);
  console.log(
    "First message content items:",
    payload.messages[0].content.length,
  );

  const response = await fetch(OPENAI_API_URL, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload),
  });

  console.log("OpenAI response status:", response.status);

  if (!response.ok) {
    const errorData = await response.text();
    console.error("OpenAI API error response:", errorData);
    try {
      const error = JSON.parse(errorData);
      throw new Error(
        `OpenAI API error (${response.status}): ${error.error?.message || response.statusText}`,
      );
    } catch (e) {
      throw new Error(
        `OpenAI API error (${response.status}): ${errorData || response.statusText}`,
      );
    }
  }

  const responseData = await response.json();
  console.log(
    "OpenAI response received. Choices:",
    responseData.choices?.length,
  );
  if (responseData.choices?.[0]?.message?.content) {
    console.log(
      "Response content (first 200 chars):",
      responseData.choices[0].message.content.substring(0, 200),
    );
  }
  return responseData;
}

/**
 * Parse the analysis response from OpenAI
 * @param {string} responseText - Raw response from OpenAI
 * @returns {object} Parsed analysis
 */
function parseAnalysisResponse(responseText) {
  try {
    console.log("=== Starting parseAnalysisResponse ===");
    console.log("Response text type:", typeof responseText);
    console.log(
      "Response text length:",
      responseText ? responseText.length : 0,
    );
    console.log("Response text (full):", responseText || "[EMPTY]");

    // Extract JSON from response (handle various formats)
    let jsonString = responseText.trim();

    // Remove markdown code blocks if present
    if (jsonString.includes("```")) {
      console.log("Found markdown code blocks, removing...");
      jsonString = jsonString
        .replace(/```json\n?/g, "")
        .replace(/```\n?/g, "")
        .trim();
      console.log("After markdown removal:", jsonString.substring(0, 100));
    }

    // Find JSON object using more precise regex
    console.log("Searching for JSON object...");
    const jsonMatch = jsonString.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      console.error("No JSON object found. Response does not contain {...}");
      throw new Error("No JSON found in response");
    }

    console.log("JSON match found, length:", jsonMatch[0].length);
    console.log("JSON content:", jsonMatch[0]);

    const analysis = JSON.parse(jsonMatch[0]);
    console.log("JSON parsed successfully");
    console.log("Parsed object keys:", Object.keys(analysis));

    // Validate response structure
    if (!analysis.risk_level) {
      console.warn("Missing risk_level in parsed response");
      throw new Error("Missing risk_level in response");
    }

    // Ensure arrays are present
    if (!Array.isArray(analysis.signals_detected)) {
      console.warn(
        "signals_detected is not an array, converting",
        analysis.signals_detected,
      );
      analysis.signals_detected = Array.isArray(analysis.signals_detected)
        ? analysis.signals_detected
        : [analysis.signals_detected].filter((x) => x);
    }
    if (!Array.isArray(analysis.flagged_comments)) {
      console.warn("flagged_comments is not an array, converting");
      analysis.flagged_comments = Array.isArray(analysis.flagged_comments)
        ? analysis.flagged_comments
        : [];
    }

    // Normalize risk level
    analysis.risk_level = analysis.risk_level.toUpperCase();
    console.log("Final parsed analysis:", analysis);
    console.log("=== parseAnalysisResponse complete ===");

    return analysis;
  } catch (error) {
    console.error("=== parseAnalysisResponse ERROR ===");
    console.error("Error message:", error.message);
    console.error("Error stack:", error.stack);
    console.error("Raw response text:", responseText);
    console.error("Response text length:", responseText?.length || 0);
    console.error("=== RETURNING SAFE DEFAULT ===");
    // Return safe default response
    return {
      risk_level: "UNKNOWN",
      signals_detected: ["Unable to parse analysis"],
      flagged_comments: [],
      summary: "Error processing response. Check browser console for details.",
    };
  }
}

console.log("OpenAI module loaded");
