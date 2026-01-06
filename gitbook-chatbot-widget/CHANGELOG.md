# Changelog

## [1.1.0] - 2026-01-06

### Added
- **Clickable result cards**: Search results now open the corresponding GitBook page in a new tab when clicked
- External link icon (↗) appears on result titles to indicate clickability
- Hover animation on result cards (slight lift effect)
- Title tooltip shows "Click to open in new tab"

### Changed
- Result cards now use the `url` field from search results to navigate to documentation pages
- Updated CSS for better visual feedback on hover and active states

### Fixed
- Search results were not opening GitBook sections when clicked (now fixed)

### Technical Details
- Modified `chatbot-widget.js` to add `window.open()` onclick handler
- Updated `chatbot-widget.css` to add external link icon and animations
- Result URLs are properly escaped to prevent XSS

---

## [1.0.0] - 2026-01-06

### Initial Release
- Full-featured chatbot widget for GitBook
- Vector search integration with FastAPI backend
- Session persistence
- Responsive design (mobile & desktop)
- Customizable colors and position
- CORS support
- Production-ready bundle

---

## How to Update

### If Using Separate Files
1. Replace `chatbot-widget.js` with the updated version
2. Replace `chatbot-widget.css` with the updated version
3. Clear browser cache or do a hard refresh (Ctrl+Shift+R)

### If Using Bundle in GitBook
1. Copy the updated code from `deploy/widget-bundle.html`
2. Replace in GitBook Settings → Custom Code → Body
3. Save and republish

### If Hosted on CDN
1. Upload the updated files to your CDN
2. The changes will propagate based on your CDN cache settings
3. Consider adding a version query parameter: `?v=1.1.0`
