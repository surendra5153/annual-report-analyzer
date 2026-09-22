# Frontend Customization Guide

## 🎨 How to Change Colors

All colors are centralized in **`frontend/src/index.css`**. Edit the CSS variables under `:root` to change the entire theme instantly.

### Location: `frontend/src/index.css`

```css
:root {
  /* Background Colors */
  --color-bg-primary: #0c0c0c;      /* Main background - change to #000000 for pure black */
  --color-bg-secondary: #1a1a1a;    /* Cards, panels */
  --color-bg-tertiary: #262626;     /* Hover states */
  
  /* Brand/Accent Colors */
  --color-primary: #e8470a;         /* Orange CTA buttons */
  --color-primary-hover: #ff5722;   /* Hover state */
  --color-primary-dim: rgba(232, 71, 10, 0.1);  /* Backgrounds */
  
  /* Text Colors */
  --color-text-primary: #ffffff;
  --color-text-secondary: #a3a3a3;
  --color-text-tertiary: #737373;
  
  /* Status Colors */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
}
```

### Quick Color Change Examples

#### Example 1: Change to Blue Theme
```css
--color-primary: #3b82f6;           /* Blue */
--color-primary-hover: #60a5fa;
--color-primary-dim: rgba(59, 130, 246, 0.1);
```

#### Example 2: Change to Purple Theme
```css
--color-primary: #8b5cf6;           /* Purple */
--color-primary-hover: #a78bfa;
--color-primary-dim: rgba(139, 92, 246, 0.1);
```

#### Example 3: Change to Green Theme
```css
--color-primary: #10b981;           /* Green */
--color-primary-hover: #34d399;
--color-primary-dim: rgba(16, 185, 129, 0.1);
```

#### Example 4: Lighter Background
```css
--color-bg-primary: #1a1a1a;        /* Lighter dark */
--color-bg-secondary: #262626;
--color-bg-tertiary: #333333;
```

---

## 🖼️ How to Add Images

### Option 1: Background Images

Add a background image to any page by editing the component file.

**Example: Dashboard with background**

Edit `frontend/src/pages/Dashboard.jsx`:

```jsx
<div 
  className="relative min-h-screen"
  style={{
    backgroundImage: 'url(/path/to/your/image.jpg)',
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed'
  }}
>
  {/* Add overlay for better text readability */}
  <div className="absolute inset-0 bg-black/60"></div>
  
  {/* Your existing content */}
  <div className="relative z-10">
    {/* ... */}
  </div>
</div>
```

### Option 2: Hero Images

Add images to cards or sections:

```jsx
<div className="relative overflow-hidden rounded-xl">
  <img 
    src="/path/to/hero.jpg" 
    alt="Hero" 
    className="w-full h-64 object-cover"
  />
  <div className="absolute inset-0 bg-gradient-to-t from-black to-transparent"></div>
  <div className="absolute bottom-4 left-4 text-white">
    <h2>Title</h2>
  </div>
</div>
```

### Option 3: Avatar/Logo Images

Replace gradient avatars with real images in `Dashboard.jsx`:

```jsx
{/* Before (gradient) */}
<div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-orange-600"></div>

{/* After (image) */}
<img 
  src="/path/to/company-logo.png" 
  alt="Company" 
  className="w-12 h-12 rounded-full object-cover"
/>
```

### Where to Store Images

1. **Public folder**: `frontend/public/images/`
   - Access with `/images/filename.jpg`
   - Best for static assets

2. **Assets folder**: `frontend/src/assets/`
   - Import in components: `import heroImg from '../assets/hero.jpg'`
   - Use with `<img src={heroImg} />`

---

## 🎭 How to Add 3D Elements

### Option 1: Spline 3D (Easiest - No Code)

1. Go to [spline.design](https://spline.design)
2. Create or use a template (e.g., rotating cube, abstract shape)
3. Export as **React component** or **embed code**
4. Add to your page:

```jsx
import Spline from '@splinetool/react-spline';

<div className="w-full h-96">
  <Spline scene="https://prod.spline.design/YOUR_SCENE_ID/scene.splinecode" />
</div>
```

**Install**: `npm install @splinetool/react-spline`

### Option 2: Three.js (Advanced Control)

1. Install Three.js:
```bash
npm install three @react-three/fiber @react-three/drei
```

2. Create a simple 3D component:

**File: `frontend/src/components/Cube3D.jsx`**

```jsx
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box } from '@react-three/drei';

export default function Cube3D() {
  return (
    <Canvas className="h-96">
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      <Box args={[1, 1, 1]}>
        <meshStandardMaterial color="#e8470a" />
      </Box>
      <OrbitControls />
    </Canvas>
  );
}
```

3. Use it in your page:

```jsx
import Cube3D from '../components/Cube3D';

<div className="my-8">
  <Cube3D />
</div>
```

### Option 3: Ready-Made 3D Models (GLTF/GLB)

1. Download free models from:
   - [Sketchfab](https://sketchfab.com/search?type=models&features=downloadable)
   - [Poly Haven](https://polyhaven.com/models)
   - [CGTrader Free](https://www.cgtrader.com/free-3d-models)

2. Load in React Three Fiber:

```jsx
import { Canvas } from '@react-three/fiber';
import { useGLTF, OrbitControls } from '@react-three/drei';

function Model() {
  const { scene } = useGLTF('/models/your-model.glb');
  return <primitive object={scene} scale={0.5} />;
}

export default function Scene3D() {
  return (
    <Canvas>
      <ambientLight />
      <Model />
      <OrbitControls />
    </Canvas>
  );
}
```

### Option 4: CSS 3D Transforms (Lightweight)

Add 3D card effects with pure CSS:

```jsx
<div 
  className="relative w-64 h-96 transition-transform duration-300 hover:scale-105"
  style={{ 
    transform: 'perspective(1000px) rotateY(10deg)',
    transformStyle: 'preserve-3d'
  }}
>
  <div className="absolute inset-0 bg-gradient-to-br from-primary to-purple-600 rounded-xl"></div>
</div>
```

---

## 🎨 Gradient & Visual Effects

### Mesh Gradients

Add modern mesh gradients to backgrounds:

```css
/* In index.css */
.mesh-gradient {
  background: 
    radial-gradient(circle at 20% 30%, rgba(232, 71, 10, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(59, 130, 246, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 50% 50%, rgba(139, 92, 246, 0.2) 0%, transparent 50%);
  background-color: #0c0c0c;
}
```

### Glassmorphism Cards

```jsx
<div className="bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
  {/* Content */}
</div>
```

### Animated Gradients

```css
.animated-gradient {
  background: linear-gradient(-45deg, #e8470a, #ff5722, #f59e0b, #ef4444);
  background-size: 400% 400%;
  animation: gradient 15s ease infinite;
}

@keyframes gradient {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
```

---

## 🎬 Advanced Animation Tips

### Parallax Scrolling

```jsx
import { useEffect, useState } from 'react';

function ParallaxSection() {
  const [scrollY, setScrollY] = useState(0);
  
  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);
  
  return (
    <div 
      style={{ 
        transform: `translateY(${scrollY * 0.5}px)` 
      }}
    >
      {/* Content */}
    </div>
  );
}
```

### Scroll-Triggered Animations

```jsx
import { useInView } from 'react-intersection-observer';

function AnimatedCard() {
  const { ref, inView } = useInView({ threshold: 0.2, triggerOnce: true });
  
  return (
    <div 
      ref={ref}
      className={`transition-all duration-700 ${
        inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
      }`}
    >
      {/* Content */}
    </div>
  );
}
```

**Install**: `npm install react-intersection-observer`

---

## 📦 Quick Wins Package Recommendations

### For Images
```bash
npm install react-lazy-load-image-component
```

### For 3D
```bash
npm install three @react-three/fiber @react-three/drei
```

### For Advanced Animations
```bash
npm install framer-motion
```

### For Particles/Effects
```bash
npm install react-tsparticles
```

---

## 🎯 Specific Component Files to Edit

| What to Change | File Location |
|---|---|
| **Dashboard hero** | `frontend/src/pages/Dashboard.jsx` |
| **Chat interface** | `frontend/src/pages/Chat.jsx` |
| **Upload page** | `frontend/src/pages/Upload.jsx` |
| **Company cards** | `frontend/src/pages/Companies.jsx` |
| **Filing details** | `frontend/src/pages/FilingDetail.jsx` |
| **Global colors** | `frontend/src/index.css` |
| **Sidebar** | `frontend/src/components/Layout.jsx` |

---

## 💡 Pro Tips

1. **Test colors in one place first**: Change only `--color-primary` in `index.css` to see the effect everywhere

2. **Use CSS variables for consistency**: Always reference `var(--color-primary)` instead of hardcoding `#e8470a`

3. **Optimize images**: Use WebP format for smaller file sizes
   - Online tool: [squoosh.app](https://squoosh.app)

4. **3D performance**: Keep polygon count low (<50k triangles) for smooth animations

5. **Accessibility**: Ensure text contrast ratio is at least 4.5:1
   - Test with: [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

---

## 🚀 Quick Start Examples

### Add a Hero Background Image Right Now

1. Add your image to `frontend/public/images/hero-bg.jpg`

2. Edit `frontend/src/pages/Dashboard.jsx`:

```jsx
// Find the hero section (around line 130)
<section className="relative py-12 px-6">
  {/* ADD THIS LINE */}
  <div className="absolute inset-0 opacity-20">
    <img src="/images/hero-bg.jpg" className="w-full h-full object-cover" />
  </div>
  
  {/* Rest of hero content */}
</section>
```

### Change Orange to Blue Right Now

Edit `frontend/src/index.css`:

```css
/* Line ~15 */
--color-primary: #3b82f6;         /* Change this */
--color-primary-hover: #60a5fa;   /* And this */
```

Save and refresh - done!

---

**Need help?** All components are in `frontend/src/` - just open any file and start experimenting!
