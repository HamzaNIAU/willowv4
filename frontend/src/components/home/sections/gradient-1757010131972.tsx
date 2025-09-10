'use client'
import React, { useRef, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Plane } from '@react-three/drei'
import { shaderMaterial } from '@react-three/drei'
import { extend } from '@react-three/fiber'
import { Color } from 'three'

// Auto-generated gradient component
// Generated at: 2025-09-04T18:25:32.628Z
// Settings: gradient-1757010131972

const vertexShader = `
varying vec2 vUv;

void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const fragmentShader = `
// Simplex 3D Noise 
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+10.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float noise(vec3 v) { 
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy,h.x);
  vec3 p1 = vec3(a0.zw,h.y);
  vec3 p2 = vec3(a1.xy,h.z);
  vec3 p3 = vec3(a1.zw,h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;
  vec4 m = max(0.5 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 105.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

uniform float uTime;
uniform float uAspect;
uniform vec3 uLightColour;
uniform vec3 uMidColour;
uniform vec3 uOffBlackColour;
uniform vec3 uBlackColour;
uniform float uScaleA;
uniform float uSpeedA;
uniform float uAmplitudeA;
uniform float uOctavesA;
uniform float uScaleB;
uniform float uSpeedB;
uniform float uAmplitudeB;
uniform float uOctavesB;
uniform float uScaleC;
uniform float uSpeedC;
uniform float uAmplitudeC;
uniform float uOctavesC;
uniform float uTurbulence;
uniform float uLacunarity;
uniform float uPersistence;
uniform float uDistortionAmount;
uniform float uDistortionScale;
uniform float uVignetteIntensity;
uniform float uVignetteSize;
uniform float uVignetteSoftness;
uniform float uGrainAmount;
uniform float uGrainSize;
uniform float uGrainSpeed;
uniform float uChromaticAberration;
uniform float uHueShift;
uniform float uSaturation;
uniform float uBrightness;
uniform float uContrast;
uniform float uWaveAmplitude;
uniform float uWaveFrequency;
uniform float uPulseSpeed;
uniform float uBreathingEffect;
uniform float uBlurAmount;
uniform float uBlurScale;
uniform float uMotionBlur;
uniform float uIntensity;
uniform float uTimeMultiplier;

varying vec2 vUv;

float fbm(vec3 p, float octaves, float lacunarity, float persistence) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (float i = 0.0; i < 8.0; i++) {
        if (i >= octaves) break;
        value += amplitude * noise(p * frequency);
        frequency *= lacunarity;
        amplitude *= persistence;
    }
    
    return value;
}

vec3 hueShift(vec3 color, float shift) {
    const vec3 k = vec3(0.57735, 0.57735, 0.57735);
    float cosAngle = cos(shift);
    return vec3(color * cosAngle + cross(k, color) * sin(shift) + k * dot(k, color) * (1.0 - cosAngle));
}

vec3 adjustSaturation(vec3 color, float saturation) {
    float gray = dot(color, vec3(0.299, 0.587, 0.114));
    return mix(vec3(gray), color, saturation);
}

vec3 adjustContrast(vec3 color, float contrast) {
    return (color - 0.5) * contrast + 0.5;
}

void main() {
    vec2 uv = vUv;
    float waveX = sin(vUv.y * uWaveFrequency + uTime * uPulseSpeed) * uWaveAmplitude;
    float waveY = cos(vUv.x * uWaveFrequency + uTime * uPulseSpeed) * uWaveAmplitude;
    uv += vec2(waveX, waveY) * 0.02;
    
    float breathing = sin(uTime * uBreathingEffect) * 0.5 + 0.5;
    
    float distortionNoise = noise(vec3(uv * uDistortionScale, uTime * 0.1));
    uv += distortionNoise * uDistortionAmount * 0.1;
    
    vec3 posA = vec3(uv * uScaleA, uTime * uSpeedA);
    float noiseA = fbm(posA, uOctavesA, uLacunarity, uPersistence);
    noiseA = noiseA * 0.5 + 0.5;
    noiseA *= uAmplitudeA;
    
    vec3 posB = vec3(uv * uScaleB, uTime * uSpeedB);
    posB += vec3(noiseA * uTurbulence);
    float noiseB = fbm(posB, uOctavesB, uLacunarity, uPersistence);
    noiseB = noiseB * 0.5 + 0.5;
    noiseB *= uAmplitudeB;
    
    vec3 posC = vec3(uv * uScaleC, uTime * uSpeedC);
    posC += vec3(noiseB * uTurbulence * 0.5);
    float noiseC = fbm(posC, uOctavesC, uLacunarity, uPersistence);
    noiseC = noiseC * 0.5 + 0.5;
    noiseC *= uAmplitudeC;
    
    float finalNoise = mix(mix(noiseA, noiseB, 0.5), noiseC, 0.33);
    finalNoise = mix(finalNoise, finalNoise * breathing, uBreathingEffect);
    
    vec3 colour1 = mix(uLightColour, uMidColour, noiseA);
    vec3 colour2 = mix(uMidColour, uOffBlackColour, noiseB);
    vec3 colour3 = mix(uOffBlackColour, uBlackColour, noiseC);
    
    vec3 colour = mix(mix(colour1, colour2, noiseB), colour3, finalNoise);
    colour = mix(uBlackColour, colour, uIntensity);
    
    if (uChromaticAberration > 0.0) {
        vec2 caOffset = vec2(uChromaticAberration, -uChromaticAberration) * 0.01;
        float rNoise = noise(vec3((uv + caOffset) * uScaleA, uTime * uSpeedA)) * 0.5 + 0.5;
        float bNoise = noise(vec3((uv - caOffset) * uScaleA, uTime * uSpeedA)) * 0.5 + 0.5;
        colour.r = mix(colour.r, mix(uLightColour.r, uMidColour.r, rNoise), uChromaticAberration);
        colour.b = mix(colour.b, mix(uLightColour.b, uMidColour.b, bNoise), uChromaticAberration);
    }
    
    vec2 vignetteUv = vUv * 2.0 - 1.0;
    vignetteUv.x *= uAspect;
    float vignette = distance(vignetteUv, vec2(0.0));
    float vig = smoothstep(uVignetteSize * 0.5, uVignetteSize + uVignetteSoftness, vignette);
    colour = mix(colour, uBlackColour, vig * uVignetteIntensity);
    
    if (uGrainAmount > 0.0) {
        float grain = noise(vec3(vUv * uGrainSize, uTime * uGrainSpeed));
        colour = colour + vec3(grain * uGrainAmount);
    }
    
    colour = hueShift(colour, uHueShift);
    colour = adjustSaturation(colour, uSaturation);
    colour = adjustContrast(colour, uContrast);
    colour = colour + uBrightness;
    colour = clamp(colour, 0.0, 1.0);
    
    gl_FragColor = vec4(colour, 1.0);
}
`

const Gradient1757010131972ShaderMaterial = shaderMaterial(
  {
    uTime: 0,
    uAspect: 1,
    uLightColour: new Color('#00ffff'),
    uMidColour: new Color('#0080ff'),
    uOffBlackColour: new Color('#0a1620'),
    uBlackColour: new Color('#040810'),
    uTimeMultiplier: 0.96,
    uIntensity: 1,
    uScaleA: 2,
    uSpeedA: 0.2,
    uAmplitudeA: 1,
    uOctavesA: 4,
    uScaleB: 4,
    uSpeedB: 0.1,
    uAmplitudeB: 1,
    uOctavesB: 3,
    uScaleC: 1,
    uSpeedC: 0.64,
    uAmplitudeC: 1,
    uOctavesC: 2,
    uTurbulence: 0.99,
    uLacunarity: 1,
    uPersistence: 0.98,
    uDistortionAmount: 0.37,
    uDistortionScale: 2.3,
    uVignetteIntensity: 0.91,
    uVignetteSize: 0.76,
    uVignetteSoftness: 0.37,
    uGrainAmount: 0.05,
    uGrainSize: 100,
    uGrainSpeed: 1,
    uChromaticAberration: 0,
    uHueShift: 0,
    uSaturation: 1,
    uBrightness: 0,
    uContrast: 1,
    uWaveAmplitude: 0,
    uWaveFrequency: 5,
    uPulseSpeed: 1,
    uBreathingEffect: 0,
    uBlurAmount: 0,
    uBlurScale: 1,
    uMotionBlur: 0,
  },
  vertexShader,
  fragmentShader
)

extend({ Gradient1757010131972ShaderMaterial })

function GradientPlane() {
  const { viewport } = useThree()
  const shader = useRef<any>(null)

  useFrame(({ clock }) => {
    if (!shader.current) return
    shader.current.uTime = clock.elapsedTime * 0.96
  })

  return (
    <Plane args={[viewport.width * 3, viewport.height * 3, 1, 1]} position={[0, 0, -6]}>
      <gradient1757010131972ShaderMaterial
        key={ Gradient1757010131972ShaderMaterial.key}
        ref={shader}
        uAspect={viewport.aspect}
      />
    </Plane>
  )
}

export default function GradientBackground({ 
  className = '',
  style = {}
}: { 
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={`w-full h-full ${className}`} style={style}>
      <Canvas
        dpr={1.5}
        camera={{ position: [0, 0, 5], far: 20 }}
        gl={{
          antialias: false,
          powerPreference: 'high-performance',
          alpha: false,
          stencil: false,
          depth: false,
        }}
      >
        <GradientPlane />
      </Canvas>
    </div>
  )
}
