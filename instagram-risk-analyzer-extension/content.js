// Content script runs on Instagram pages
// Responsible for extracting visible content from the DOM

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extractContent") {
    const content = extractInstagramContent();
    sendResponse(content);
  }
});

/**
 * Extract all visible content from Instagram profile
 * Returns object with profile info, captions, comments, and image descriptions
 */
function extractInstagramContent() {
  const content = {
    profileBio: extractProfileBio(),
    posts: extractPostsContent(),
    visibleComments: extractVisibleComments(),
    pageUrl: window.location.href,
    extractedAt: new Date().toISOString(),
  };

  return content;
}

/**
 * Extract profile bio from header
 */
function extractProfileBio() {
  let bio = "";

  // Try common Instagram profile bio selectors
  const bioSelectors = [
    "header section span",
    '[data-testid="bio"]',
    "main header span",
    "h2 + div span",
  ];

  for (const selector of bioSelectors) {
    const element = document.querySelector(selector);
    if (element) {
      const text = element.textContent.trim();
      if (text && text.length > 0) {
        bio = text;
        break;
      }
    }
  }

  return bio;
}

/**
 * Extract captions and metadata from visible posts
 */
function extractPostsContent() {
  const posts = [];
  const postElements = document.querySelectorAll("article");

  postElements.forEach((article, index) => {
    if (posts.length >= 20) return; // Limit to first 20 posts visible

    const post = {
      index: index,
      caption: extractCaption(article),
      altTexts: extractImageAltTexts(article),
      links: extractPostLinks(article),
    };

    // Only add if we have content
    if (post.caption || post.altTexts.length > 0) {
      posts.push(post);
    }
  });

  return posts;
}

/**
 * Extract caption text from a post article element
 */
function extractCaption(article) {
  let caption = "";

  // Try to find caption text near the article
  const captionSelectors = [
    'span[data-testid="post-text"]',
    "span h1",
    "article span:nth-of-type(1)",
    'div[role="menuitem"] span',
  ];

  for (const selector of captionSelectors) {
    const element = article.querySelector(selector);
    if (element) {
      const text = element.textContent.trim();
      if (text && text.length > 0) {
        caption = text;
        break;
      }
    }
  }

  // Fallback: get all text from article and filter
  if (!caption) {
    const allText = article.innerText;
    // Remove common Instagram UI text
    const filtered = allText
      .split("\n")
      .filter((line) => line.length > 5 && !line.includes("Like"))
      .slice(0, 2)
      .join(" ");
    caption = filtered;
  }

  return caption;
}

/**
 * Extract alt text from images (important for accessibility and content description)
 */
function extractImageAltTexts(article) {
  const altTexts = [];
  const images = article.querySelectorAll("img");

  images.forEach((img) => {
    if (img.alt && img.alt.trim().length > 0) {
      altTexts.push(img.alt);
    }
  });

  return altTexts;
}

/**
 * Extract links and hashtags from post
 */
function extractPostLinks(article) {
  const links = [];
  const anchors = article.querySelectorAll("a");

  anchors.forEach((anchor) => {
    const href = anchor.getAttribute("href");
    const text = anchor.textContent.trim();

    // Capture hashtags and mentions
    if ((text.startsWith("#") || text.startsWith("@")) && text.length > 1) {
      links.push(text);
    }
  });

  return links;
}

/**
 * Extract visible comments from the current view
 * Note: Comments are lazy-loaded on Instagram, so we only get currently visible ones
 */
function extractVisibleComments() {
  const comments = [];
  const commentSelectors = [
    '[data-testid="comment"]',
    'div[role="article"] span[aria-label*="comment"]',
    "ul li div span",
  ];

  // Try different selectors
  for (const selector of commentSelectors) {
    const elements = document.querySelectorAll(selector);
    if (elements.length > 0) {
      elements.forEach((element) => {
        const text = element.textContent.trim();
        // Filter for meaningful comments (not too short)
        if (
          text.length > 5 &&
          text.length < 500 &&
          !text.includes("View replies")
        ) {
          // Remove duplicate comments
          if (!comments.includes(text)) {
            comments.push(text);
          }
        }
      });
      break;
    }
  }

  // Limit to first 50 visible comments
  return comments.slice(0, 50);
}

console.log("Instagram Content Extractor loaded and ready");
