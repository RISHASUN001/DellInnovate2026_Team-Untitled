#  CaptchaGram! Chrome Extension

A Chrome Extension to assist youth outreach volunteers in identifying potential mental health risk signals on Instagram profiles they are viewing.

## ⚠️ Important Disclaimer

This tool is **NOT a diagnostic instrument**. It is a screening aid that identifies potential concerning patterns in visible Instagram content. Any findings should be evaluated by trained mental health professionals. Always follow proper protocols and safeguarding procedures when responding to identified risk signals.

## Features

- **Analyzes visible Instagram content** including:
  - Profile biography
  - Post captions
  - Visible comments
  - Image descriptions and alt text
  - Screenshot of current view

- **OpenAI-powered analysis** for:
  - Identifying potential risk signals
  - Detecting concerning language
  - Flagging problematic comments
  - Computing risk assessment levels

- **Color-coded risk levels**:
  - 🟢 **LOW**: No concerning signals detected
  - 🟡 **MEDIUM**: Some signals present requiring attention
  - 🟠 **HIGH**: Multiple concerning signals
  - 🔴 **CRITICAL**: Severe signals suggesting immediate risk

- **Privacy-focused**:
  - Analyzes only visible DOM content
  - No automated scraping
  - No permanent data storage
  - Respects Instagram's terms of service

## Installation

### Prerequisites

- Chrome browser
- OpenAI API key (from [platform.openai.com](https://platform.openai.com/api-keys))
- Optional: OpenAI Organization ID

### Setup Steps

1. **Create the extension folder** (already done at `/instagram-risk-analyzer-extension/`)

2. **Configure your API credentials**:

   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your actual OpenAI API key
   # OPENAI_API_KEY=sk-proj-your-key-here
   ```

3. **Load the extension in Chrome**:
   - Open `chrome://extensions/`
   - Enable "Developer mode" (top right)
   - Click "Load unpacked"
   - Select the `instagram-risk-analyzer-extension` folder
   - The extension icon will appear in your toolbar

4. **Configure in the extension**:
   - Click the extension icon
   - Paste your OpenAI API Key in the settings
   - Optionally add your Organization ID
   - Click "Save Settings"

## Usage

1. Navigate to an Instagram profile
2. Click the extension icon
3. Click **"Analyze Current Profile"**
4. Wait for the analysis to complete
5. Review the risk assessment and identified signals

## File Structure

```
instagram-risk-analyzer-extension/
├── manifest.json           # Extension configuration
├── popup.html             # Settings and results UI
├── popup.js               # UI logic and interactions
├── content.js             # Content extraction from Instagram
├── background.js          # Extension lifecycle management
├── openai.js              # OpenAI API integration
├── styles.css             # UI styling
├── .env.example           # Example environment variables
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## Technical Details

### Manifest V3 Permissions

- `activeTab` - Access current tab
- `scripting` - Execute content scripts
- `tabs` - Get tab information
- `storage` - Store API key locally
- `host_permissions` - Access Instagram.com

### Content Extraction

The extension extracts:

**Profile Information:**

- Bio/About section
- Visible post captions
- Image descriptions
- Hashtags and mentions

**Comments:**

- Currently visible comments (lazy-loaded on Instagram)
- Limited to 50 most recent visible comments

**Media:**

- Visible image alt-text
- Screenshot of current viewport

### OpenAI Analysis

The extension uses OpenAI's vision model to:

1. **Analyze the screenshot** for visual indicators
2. **Process extracted text** for linguistic patterns
3. **Identify risk signals** based on trained understanding
4. **Return structured analysis** with risk level and explanation

### Storage

- API key stored locally in Chrome (never transmitted except to OpenAI)
- Analysis results displayed in popup (not persisted)
- No Instagram data stored after analysis completes

## Security Considerations

⚠️ **API Key Safety:**

- API key is stored locally in browser storage
- Never commit `.env` to version control
- Keep your API key confidential
- Monitor your OpenAI usage for unauthorized access

**Privacy:**

- Plugin does not upload Instagram data to servers (except OpenAI)
- Screenshot analysis by OpenAI follows their data retention policies
- See [OpenAI Privacy Policy](https://openai.com/privacy)

## Troubleshooting

### Extension won't load

- Verify manifest.json syntax is valid
- Check Chrome is in Developer mode
- Clear Chrome cache if updating extension

### "API key not configured" error

- Open extension popup
- Enter your OpenAI API key
- Click "Save Settings"

### Analysis fails

- Verify your OpenAI API key is valid
- Check your OpenAI account has credits
- Ensure you're on an Instagram profile page
- Check browser console for error messages

### Cannot extract content

- Verify page is fully loaded before clicking "Analyze"
- Instagram content is dynamically loaded; scroll to load posts
- Some Instagram UI changes may affect selector accuracy
- Try refreshing the Instagram page and trying again

## Limitations

1. **Comment availability** - Only visible comments can be extracted; Instagram uses lazy loading
2. **Image analysis** - Limited to visible images; requires Alt-text or screenshot analysis
3. **Dynamic content** - Must analyze after page fully loads
4. **Rate limits** - OpenAI API rate limits apply

## API Costs

Each analysis uses OpenAI API credits. Estimated costs per analysis:

- Vision model call: ~0.01-0.03 USD
- Text analysis: ~0.001-0.005 USD

Monitor your usage at [OpenAI Usage Dashboard](https://platform.openai.com/account/billing/overview)

## Development

### Modifying the extension

1. Make changes to source files
2. Go to `chrome://extensions/`
3. Click reload button for the extension
4. Test changes in Chrome

### Key files to understand:

- **popup.js** - Main UI logic, handles buttons and displays results
- **content.js** - Extracts content from Instagram DOM
- **openai.js** - Communicates with OpenAI API
- **manifest.json** - Defines extension capabilities and permissions

## Support Information

For issues with:

- **Extension functionality** - Check troubleshooting section
- **OpenAI API** - Visit [OpenAI Help Center](https://help.openai.com)
- **Instagram selectors** - May need updating if Instagram UI changes

## Ethical Guidelines

This tool is designed to support youth outreach professionals:

✅ **Do:**

- Use as a supplementary screening tool
- Follow established safeguarding procedures
- Involve trained mental health professionals
- Maintain confidentiality and privacy

❌ **Don't:**

- Use as a diagnosis tool
- Override professional judgment
- Share risk assessments without proper authorization
- Isolate decision-making from professional oversight

## Future Enhancements

Possible improvements for future versions:

- Batch analysis of multiple profiles
- Export analysis reports
- Custom risk criteria configuration
- Comment timeline analysis
- Integration with case management systems
- Accessibility improvements

## License

This extension is provided as-is for authorized users only.

## Contact & Support

For questions or issues, contact your organization's administrator.

---

**Version:** 1.0.0  
**Last Updated:** March 2026  
**Status:** Beta - Community Testing
