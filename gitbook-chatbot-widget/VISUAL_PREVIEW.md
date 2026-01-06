# Visual Preview

## What Users Will See

### 1. Closed State (Initial)
```
┌─────────────────────────────────────────────────────┐
│                                                      │
│  GitBook Documentation Page                         │
│                                                      │
│  Content about your product...                      │
│  More documentation...                              │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                           ┌────┐    │
│                                           │ 💬 │    │
│                                           └────┘    │
└─────────────────────────────────────────────────────┘
```

### 2. Open Chat Window
```
┌─────────────────────────────────────────────────────┐
│                                                      │
│  GitBook Documentation                 ┌──────────┐ │
│                                        │ Doc Asst │ │
│  Content continues...                  │ Ask me.. │ │
│                                        ├──────────┤ │
│                                        │          │ │
│                                        │ 🤖 Hi!   │ │
│                                        │ I can..  │ │
│                                        │          │ │
│                                        │   👤     │ │
│                                        │ How do I │ │
│                                        │ auth?    │ │
│                                        │          │ │
│                                        │ 🤖       │ │
│                                        │ I found  │ │
│                                        │ 5 res... │ │
│                                        │ ┌──────┐ │ │
│                                        │ │Title │ │ │
│                                        │ │Cont..│ │ │
│                                        │ └──────┘ │ │
│                                        ├──────────┤ │
│                                        │ Type...🔵│ │
│                                        └──────────┘ │
│                                           ┌────┐    │
│                                           │ X  │    │
└──────────────────────────────────────────└────┘────┘
```

## Actual Component Breakdown

### Chat Toggle Button
```
     ╔════════╗
     ║   💬   ║  ← Floating button
     ║        ║     Size: 60x60px
     ╚════════╝     Color: #0066cc
        (1)           Position: bottom-right
```

### Chat Window (Expanded)
```
╔══════════════════════════════════════════╗
║  Documentation Assistant          [X]    ║  ← Header (blue)
║  Ask me anything about the docs          ║     16px padding
╠══════════════════════════════════════════╣
║                                          ║
║  🤖  Hi! I can help you find            ║  ← Bot message
║      information...                     ║     White bubble
║      11:23 AM                           ║
║                                          ║
║                              👤  How do  ║  ← User message
║                         I configure auth?║     Blue bubble
║                                  11:24 AM║
║                                          ║  ← Messages area
║  🤖  I found 5 relevant results:        ║     Scrollable
║                                          ║
║      ┌────────────────────────────────┐ ║
║      │ Getting Started                │ ║  ← Result card
║      │ Configure authentication by... │ ║     Clickable
║      │ Module › Section              │ ║     Hover effect
║      └────────────────────────────────┘ ║
║      ┌────────────────────────────────┐ ║
║      │ Authentication Guide           │ ║
║      │ To set up auth, first...       │ ║
║      └────────────────────────────────┘ ║
║                                          ║
╠══════════════════════════════════════════╣
║ ┌──────────────────────────────────┐ 🔵 ║  ← Input area
║ │ Type your question...            │    ║     Send button
║ └──────────────────────────────────┘    ║
╚══════════════════════════════════════════╝
```

### Typing Indicator
```
🤖  ● ● ●  ← Animated dots while bot is "thinking"
```

### Color Scheme (Default)
```
Primary Color:    #0066cc  ████ (Blue)
Secondary Color:  #f5f5f5  ████ (Light Gray)
User Message:     #0066cc  ████ (Blue)
Bot Message:      #e8f4fd  ████ (Light Blue)
Text Color:       #333333  ████ (Dark Gray)
Border:           #e0e0e0  ████ (Gray)
White:            #ffffff  ████ (White)
```

## Mobile View
```
┌─────────────────────────┐
│ GitBook Docs            │
│                         │
│ Content...              │
│                         │
│ ┌─────────────────────┐ │
│ │ Doc Assistant   [X] │ │
│ ├─────────────────────┤ │
│ │                     │ │
│ │ 🤖 Hi! I can help  │ │
│ │                     │ │
│ │        👤 Question? │ │
│ │                     │ │
│ │ 🤖 I found 3 res..  │ │
│ │ ┌─────────────────┐ │ │
│ │ │ Result 1        │ │ │
│ │ └─────────────────┘ │ │
│ │ ┌─────────────────┐ │ │
│ │ │ Result 2        │ │ │
│ │ └─────────────────┘ │ │
│ ├─────────────────────┤ │
│ │ Type here...     🔵 │ │
│ └─────────────────────┘ │
│            💬           │
└─────────────────────────┘
```

## User Interaction Flow

```
User Opens GitBook
        │
        ▼
Sees Floating Chat Button (bottom-right)
        │
        ▼
Clicks Chat Button
        │
        ▼
Chat Window Slides Up ↑
        │
        ▼
Sees Welcome Message from Bot
        │
        ▼
Types Question in Input Field
        │
        ▼
Clicks Send Button (or presses Enter)
        │
        ▼
Message Appears in Chat (user bubble)
        │
        ▼
Bot Shows Typing Indicator (● ● ●)
        │
        ▼
API Call to /v1/search
        │
        ▼
Results Appear as Cards
        │
        ▼
User Clicks Result Card
        │
        ▼
(Could navigate to doc or show more info)
```

## Animation Examples

### Slide Up Animation (Chat Opening)
```
Frame 1:  [Hidden]
Frame 2:  [Opacity: 0.2, Y: +20px]
Frame 3:  [Opacity: 0.5, Y: +10px]
Frame 4:  [Opacity: 0.8, Y: +5px]
Frame 5:  [Opacity: 1.0, Y: 0px] ← Fully visible
```

### Typing Dots Animation
```
Time 0s:  ● · ·
Time 0.2s: · ● ·
Time 0.4s: · · ●
Time 0.6s: ● · ·  (repeats)
```

### Message Fade In
```
Frame 1:  [Opacity: 0, Y: +10px]
Frame 2:  [Opacity: 0.3, Y: +7px]
Frame 3:  [Opacity: 0.6, Y: +4px]
Frame 4:  [Opacity: 1.0, Y: 0px] ← Fully visible
```

## Responsive Breakpoints

### Desktop (> 480px)
- Widget Width: 380px
- Widget Height: 550px
- Position: Fixed, bottom-right (20px from edges)

### Mobile (<= 480px)
- Widget Width: calc(100vw - 20px)
- Widget Height: calc(100vh - 90px)
- Position: Nearly full screen
- Positioned: 10px from all edges

## States & Variations

### Normal State
```
┌────┐
│ 💬 │  Blue button, shadow
└────┘
```

### Hover State
```
┌────┐
│ 💬 │  Slightly larger (scale 1.05)
└────┘  Bigger shadow
```

### With Unread Badge
```
┌────┐
│ 💬 │ (1) ← Red badge with count
└────┘
```

### Disabled/Loading State
```
┌────┐
│ ⌛ │  Gray button
└────┘  No click
```

## Example Conversation

```
╔════════════════════════════════════════╗
║ Documentation Assistant            [X] ║
╠════════════════════════════════════════╣
║                                        ║
║ 🤖  Hi! I can help you find           ║
║     information in the documentation. ║
║     What would you like to know?      ║
║     11:20 AM                          ║
║                                        ║
║                     👤  How do I      ║
║                   configure auth?     ║
║                         11:21 AM      ║
║                                        ║
║ 🤖  I found 5 relevant results:       ║
║                                        ║
║ ┌────────────────────────────────────┐ ║
║ │ ⭐ Getting Started                 │ ║
║ │ Configure authentication by        │ ║
║ │ navigating to Settings > Auth...   │ ║
║ │ 📍 Administration › Security       │ ║
║ └────────────────────────────────────┘ ║
║                                        ║
║ ┌────────────────────────────────────┐ ║
║ │ ⭐ Authentication Guide            │ ║
║ │ To set up authentication, you      │ ║
║ │ need to first create an API...     │ ║
║ │ 📍 API Reference › Auth            │ ║
║ └────────────────────────────────────┘ ║
║                                        ║
║ ┌────────────────────────────────────┐ ║
║ │ ⭐ OAuth Configuration             │ ║
║ │ For OAuth 2.0 setup, follow...    │ ║
║ │ 📍 Security › OAuth                │ ║
║ └────────────────────────────────────┘ ║
║     11:21 AM                          ║
║                                        ║
║                     👤  Thanks!       ║
║                         11:22 AM      ║
║                                        ║
║ 🤖  You're welcome! Let me know      ║
║     if you need anything else.        ║
║     11:22 AM                          ║
║                                        ║
╠════════════════════════════════════════╣
║ ┌──────────────────────────────────┐🔵║
║ │ Type your question...            │  ║
║ └──────────────────────────────────┘  ║
╚════════════════════════════════════════╝
```

## Integration Preview

### Before Integration
```
┌─────────────────────────────────────────┐
│ GitBook Documentation                   │
│                                         │
│ Your docs content here...               │
│                                         │
│ (Just regular GitBook pages)            │
│                                         │
└─────────────────────────────────────────┘
```

### After Integration
```
┌─────────────────────────────────────────┐
│ GitBook Documentation                   │
│                                         │
│ Your docs content here...               │
│                                         │
│ (Same content, plus chatbot!)           │
│                                  ┌────┐ │
│                                  │ 💬 │ │
│                                  └────┘ │
└─────────────────────────────────────────┘
```

---

## Try It Now!

Run this command to see it live:

```bash
cd gitbook-chatbot-widget
python -m http.server 8080
```

Then open: http://localhost:8080/demo.html

The demo page includes:
- ✅ Full working chatbot
- ✅ Sample documentation layout
- ✅ Feature explanations
- ✅ Configuration examples
- ✅ Status indicators

---

**Visual design inspired by:**
- Intercom
- Crisp Chat
- Drift
- GitBook's own design system

**Optimized for:**
- Fast loading
- Minimal footprint
- Accessibility
- Mobile devices
- Low bandwidth
