# 🖼️ Image Integration Guide

## 📁 Folder Structure

```
frontend/
├── public/
│   └── images/
│       ├── logo.png              ← Your logo (120x120px recommended)
│       ├── dashboard-bg.png      ← Dashboard background
│       ├── upload-bg.png         ← Upload page background (optional)
│       ├── chat-bg.png           ← Chat page background (optional)
│       ├── compare-bg.png        ← Compare page background (optional)
│       └── hero-illustration.png ← Hero section image (optional)
```

## ✅ Already Integrated

### 1. **Logo** (Layout.jsx)
- **Location**: Sidebar (desktop) + Mobile header
- **File**: `/images/logo.png`
- **Fallback**: Orange icon (FileBarChart2) if image not found
- **Size**: 28x28px (displays as 7x7 Tailwind units)

### 2. **Dashboard Background** (Dashboard.jsx)
- **Location**: Full-page background (very subtle - 3% opacity)
- **File**: `/images/dashboard-bg.png`
- **Effect**: Subtle texture/pattern behind content
- **Size**: 1920x1080px recommended

---

## 🎨 How to Add Images to Other Pages

### **Upload Page Background**

Edit `frontend/src/pages/Upload.jsx`:

```jsx
// Add after the opening <div className="page-container">
<div style={{
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundImage: 'url(/images/upload-bg.png)',
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  opacity: 0.05, // Adjust opacity as needed
  pointerEvents: 'none',
  zIndex: -1
}} />
```

### **Chat Page Background**

Edit `frontend/src/pages/Chat.jsx`:

```jsx
// Add at the top of the return statement
<div style={{
  position: 'fixed',
  inset: 0,
  backgroundImage: 'url(/images/chat-bg.png)',
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  opacity: 0.04,
  pointerEvents: 'none',
  zIndex: -1
}} />
```

### **Compare Page Background**

Edit `frontend/src/pages/Compare.jsx`:

```jsx
// Add after <div className="page-container">
<div style={{
  position: 'fixed',
  inset: 0,
  backgroundImage: 'url(/images/compare-bg.png)',
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  opacity: 0.03,
  pointerEvents: 'none',
  zIndex: -1
}} />
```

---

## 🎯 Dashboard Hero Image (Alternative to Lottie)

If you want to use a static image instead of Lottie animation on the Dashboard hero:

Edit `frontend/src/pages/Dashboard.jsx`:

Replace the Lottie animation section with:

```jsx
{/* Hero Image instead of Lottie */}
<div className="mobile-hidden" style={{ 
  width: 280, 
  height: 220, 
  flexShrink: 0,
  borderRadius: 16,
  overflow: 'hidden'
}}>
  <img 
    src="/images/hero-illustration.png" 
    alt="Dashboard Illustration"
    style={{
      width: '100%',
      height: '100%',
      objectFit: 'cover',
      opacity: 0.9
    }}
  />
</div>
```

---

## 🎨 Advanced: CSS Background Patterns

### **Body Background Texture**

Add to `frontend/src/index.css`:

```css
body {
  /* ... existing styles ... */
  background-image: url('/images/noise-texture.png');
  background-repeat: repeat;
  background-size: 200px 200px;
}
```

### **Card Background Image**

```css
.card {
  /* ... existing styles ... */
  background-image: 
    linear-gradient(rgba(62, 60, 60, 0.35), rgba(62, 60, 60, 0.35)),
    url('/images/card-pattern.png');
  background-size: cover;
}
```

---

## 📐 Image Size Recommendations

| Image | Recommended Size | Format | Notes |
|-------|-----------------|--------|-------|
| **Logo** | 120x120px | PNG (transparent) | Square, clean design |
| **Dashboard BG** | 1920x1080px | JPG/PNG | Abstract, low contrast |
| **Upload BG** | 1920x1080px | JPG/PNG | Document/upload theme |
| **Chat BG** | 1920x1080px | JPG/PNG | Conversation bubbles theme |
| **Compare BG** | 1920x1080px | JPG/PNG | Charts/graphs theme |
| **Hero Illustration** | 800x600px | PNG/SVG | High quality, transparent BG |
| **Noise Texture** | 200x200px | PNG | Seamless tile |

---

## 🎨 Image Optimization Tips

### 1. **Optimize File Size**
```bash
# Using TinyPNG or similar
- Dashboard BG: < 200KB
- Logo: < 50KB
- Other BGs: < 150KB each
```

### 2. **Use WebP Format (Modern)**
```jsx
<img 
  src="/images/logo.webp" 
  alt="Logo"
  onError={(e) => e.target.src = '/images/logo.png'} // PNG fallback
/>
```

### 3. **Lazy Load Background Images**
```jsx
useEffect(() => {
  const img = new Image()
  img.src = '/images/dashboard-bg.png'
  img.onload = () => {
    document.getElementById('bg').style.backgroundImage = `url(${img.src})`
  }
}, [])
```

---

## 🚀 Quick Setup Steps

### **Step 1: Place Your Images**
1. Copy your logo to: `frontend/public/images/logo.png`
2. Copy dashboard background to: `frontend/public/images/dashboard-bg.png`
3. (Optional) Add other page backgrounds

### **Step 2: Verify**
- Logo appears in sidebar and mobile header
- Dashboard shows subtle background texture
- If image missing, fallback icon displays

### **Step 3: Adjust Opacity**
Fine-tune background opacity in each page:
- **Dashboard**: Currently 0.03 (very subtle)
- **Upload**: Suggested 0.05
- **Chat**: Suggested 0.04
- **Compare**: Suggested 0.03

Lower = more subtle, Higher = more visible

---

## 🎨 Example: Full Page Background Pattern

For a more dramatic effect with your images:

```jsx
<div style={{
  position: 'fixed',
  inset: 0,
  background: `
    radial-gradient(circle at 20% 50%, rgba(232, 71, 10, 0.05) 0%, transparent 50%),
    radial-gradient(circle at 80% 50%, rgba(99, 102, 241, 0.03) 0%, transparent 50%),
    url('/images/dashboard-bg.png')
  `,
  backgroundSize: 'cover',
  backgroundPosition: 'center',
  pointerEvents: 'none',
  zIndex: -2
}} />
```

---

## 🔍 Troubleshooting

### **Image Not Showing?**
1. Check file path: Must be in `frontend/public/images/`
2. Check file name: Case-sensitive on Linux/Mac
3. Clear browser cache: Ctrl+Shift+R (hard refresh)
4. Check console for 404 errors

### **Image Too Visible?**
- Reduce `opacity` value (try 0.02 - 0.05)
- Use `filter: grayscale(100%)` for monochrome effect
- Apply blur: `filter: blur(2px)`

### **Performance Issues?**
- Optimize image size (< 200KB)
- Use WebP format
- Consider using CSS gradients instead

---

## 📝 Current File Structure

```
frontend/
├── public/
│   └── images/
│       ├── logo.png                    ✅ Integrated (with fallback)
│       ├── dashboard-bg.png            ✅ Integrated
│       ├── upload-bg.png               🔲 Add manually
│       ├── chat-bg.png                 🔲 Add manually
│       ├── compare-bg.png              🔲 Add manually
│       └── README.md                   ✅ Created
├── src/
│   ├── components/
│   │   └── Layout.jsx                  ✅ Logo integrated
│   └── pages/
│       └── Dashboard.jsx               ✅ Background integrated
│
└── IMAGE_INTEGRATION_GUIDE.md          ✅ This file
```

---

## ✨ Next Steps

1. **Place your images** in `frontend/public/images/`
2. **Test the logo** - should appear in sidebar/header
3. **Check dashboard background** - should be very subtle
4. **Add backgrounds to other pages** using the code snippets above
5. **Adjust opacity** values to your preference
6. **Optimize images** for web (compress, resize)

---

**Need help?** Check if images exist at: `http://localhost:3000/images/logo.png`

**Last Updated**: September 22, 2026
