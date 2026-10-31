import React, { useEffect, useRef, useState, useCallback } from "react";

interface DitherRevealProps {
  src?: string;
  alt?: string;
  className?: string;
  durationMs?: number;
  revealDelayMs?: number;
  maxDrift?: number;
}

const VS_SOURCE = `
attribute vec2 a_position;
varying vec2 v_uv;

void main() {
  v_uv = (a_position + 1.0) * 0.5;
  v_uv.y = 1.0 - v_uv.y;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const FS_SOURCE = `
precision highp float;
varying vec2 v_uv;

uniform sampler2D u_image;
uniform float u_progress;
uniform vec2 u_resolution;
uniform vec2 u_image_resolution;
uniform vec2 u_offset;
uniform float u_shadow_dither;

float bayer4(vec2 p) {
  vec2 m = mod(p, 4.0);
  int x = int(m.x);
  int y = int(m.y);
  if (y == 0) {
    if (x == 0) return 0.0 / 16.0;
    if (x == 1) return 8.0 / 16.0;
    if (x == 2) return 2.0 / 16.0;
    return 10.0 / 16.0;
  } else if (y == 1) {
    if (x == 0) return 12.0 / 16.0;
    if (x == 1) return 4.0 / 16.0;
    if (x == 2) return 14.0 / 16.0;
    return 6.0 / 16.0;
  } else if (y == 2) {
    if (x == 0) return 3.0 / 16.0;
    if (x == 1) return 11.0 / 16.0;
    if (x == 2) return 1.0 / 16.0;
    return 9.0 / 16.0;
  } else {
    if (x == 0) return 15.0 / 16.0;
    if (x == 1) return 7.0 / 16.0;
    if (x == 2) return 13.0 / 16.0;
    return 5.0 / 16.0;
  }
}

float bayer2(vec2 p) {
  vec2 m = mod(p, 2.0);
  int x = int(m.x);
  int y = int(m.y);
  if (y == 0) {
    return (x == 0) ? 0.0 / 4.0 : 2.0 / 4.0;
  } else {
    return (x == 0) ? 3.0 / 4.0 : 1.0 / 4.0;
  }
}

float bayer8(vec2 p) {
  vec2 p4 = mod(p, 4.0);
  vec2 p2 = floor(mod(p, 8.0) / 4.0);
  return (4.0 * bayer4(p4) + bayer2(p2)) / 5.0;
}

void main() {
  vec2 s = u_resolution;
  vec2 i = u_image_resolution;
  
  float r_canvas = s.x / s.y;
  float r_image = i.x / i.y;
  
  vec2 ratio = vec2(
    max(r_canvas / r_image, 1.0),
    max(r_image / r_canvas, 1.0)
  );
  
  vec2 drift = (u_offset / s) * 0.75;
  vec2 uv = (v_uv - 0.5 - drift) * ratio + 0.5;
  
  vec3 bg = vec3(11.0 / 255.0, 11.0 / 255.0, 13.0 / 255.0);
  
  if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
    gl_FragColor = vec4(bg, 1.0);
    return;
  }
  
  vec4 color = texture2D(u_image, uv);
  float lum = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  
  float bgMask = smoothstep(0.015, 0.08, lum);
  if (bgMask < 0.01) {
    gl_FragColor = vec4(bg, 1.0);
    return;
  }
  
  vec2 ditherCoord = floor(gl_FragCoord.xy / 2.0);
  float dither = bayer8(ditherCoord);
  
  float sweep = clamp(u_progress, 0.0, 1.0);
  
  float ditherStep = step(dither, lum * (0.28 + sweep * 0.78));
  vec3 ditherColor = mix(bg, vec3(0.92, 0.94, 0.98), ditherStep);
  
  vec3 chromeColor = pow(color.rgb, vec3(0.95)) * 1.06;
  
  float shadowZone = smoothstep(0.38, 0.06, lum);
  float shadowStipple = step(dither * 0.82 + 0.12, lum * 2.3);
  vec3 shadowTextureColor = mix(bg, chromeColor, shadowStipple);
  vec3 postRevealColor = mix(chromeColor, shadowTextureColor, shadowZone * u_shadow_dither);
  
  float revealCutoff = smoothstep(0.0, 1.0, (sweep * 1.45) - (1.0 - lum) * 0.55);
  vec3 finalRgb = mix(ditherColor, postRevealColor, revealCutoff);
  
  vec3 outColor = mix(bg, finalRgb, bgMask);
  gl_FragColor = vec4(outColor, 1.0);
}
`;

function createShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("Shader compile error:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export const DitherReveal: React.FC<DitherRevealProps> = ({
  src = "/chrome-hands.png",
  alt = "Two liquid chrome hands reaching toward each other in a pitch-deck agency hero with Bayer halftone dither reveal",
  className = "",
  durationMs = 1600,
  revealDelayMs = 150,
  maxDrift = 18,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [webGlFailed, setWebGlFailed] = useState(false);

  // Mouse drift state
  const mouseTargetRef = useRef({ x: 0, y: 0 });
  const mouseCurrentRef = useRef({ x: 0, y: 0 });

  // Handle cursor drift
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const { innerWidth, innerHeight } = window;
    const nx = (e.clientX / innerWidth - 0.5) * 2;
    const ny = (e.clientY / innerHeight - 0.5) * 2;
    mouseTargetRef.current = {
      x: nx * maxDrift,
      y: ny * maxDrift,
    };
  }, [maxDrift]);

  useEffect(() => {
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [handleMouseMove]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Load Image
    const img = new Image();
    img.src = src;
    img.crossOrigin = "anonymous";

    let animId: number;
    let gl: WebGLRenderingContext | null = null;
    let program: WebGLProgram | null = null;
    let startTime: number | null = null;

    img.onload = () => {
      setIsLoaded(true);

      gl = canvas.getContext("webgl", { alpha: false, antialias: false, premultipliedAlpha: false });
      if (!gl) {
        setWebGlFailed(true);
        return;
      }

      const vs = createShader(gl, gl.VERTEX_SHADER, VS_SOURCE);
      const fs = createShader(gl, gl.FRAGMENT_SHADER, FS_SOURCE);
      if (!vs || !fs) {
        setWebGlFailed(true);
        return;
      }

      program = gl.createProgram();
      if (!program) {
        setWebGlFailed(true);
        return;
      }

      gl.attachShader(program, vs);
      gl.attachShader(program, fs);
      gl.linkProgram(program);

      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        console.error("Program link error:", gl.getProgramInfoLog(program));
        setWebGlFailed(true);
        return;
      }

      gl.useProgram(program);

      // Full-screen quad buffer
      const positionBuffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      const positions = new Float32Array([
        -1.0, -1.0,
         1.0, -1.0,
        -1.0,  1.0,
        -1.0,  1.0,
         1.0, -1.0,
         1.0,  1.0,
      ]);
      gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

      const aPositionLoc = gl.getAttribLocation(program, "a_position");
      gl.enableVertexAttribArray(aPositionLoc);
      gl.vertexAttribPointer(aPositionLoc, 2, gl.FLOAT, false, 0, 0);

      // Texture upload
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);

      // Uniforms
      const uImageLoc = gl.getUniformLocation(program, "u_image");
      const uProgressLoc = gl.getUniformLocation(program, "u_progress");
      const uResolutionLoc = gl.getUniformLocation(program, "u_resolution");
      const uImgResLoc = gl.getUniformLocation(program, "u_image_resolution");
      const uOffsetLoc = gl.getUniformLocation(program, "u_offset");
      const uShadowDitherLoc = gl.getUniformLocation(program, "u_shadow_dither");

      gl.uniform1i(uImageLoc, 0);
      gl.uniform2f(uImgResLoc, img.naturalWidth || 1376, img.naturalHeight || 768);
      gl.uniform1f(uShadowDitherLoc, 0.78);

      const updateSize = () => {
        if (!canvas) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const rect = canvas.getBoundingClientRect();
        const displayWidth = Math.floor(rect.width * dpr);
        const displayHeight = Math.floor(rect.height * dpr);

        if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
          canvas.width = displayWidth;
          canvas.height = displayHeight;
          if (gl) {
            gl.viewport(0, 0, displayWidth, displayHeight);
          }
        }
      };

      updateSize();
      window.addEventListener("resize", updateSize);

      const render = (time: number) => {
        if (!startTime) startTime = time + revealDelayMs;
        if (!gl || !program) return;

        // Smooth easing for mouse drift
        if (prefersReducedMotion) {
          mouseCurrentRef.current = { x: 0, y: 0 };
        } else {
          mouseCurrentRef.current.x += (mouseTargetRef.current.x - mouseCurrentRef.current.x) * 0.06;
          mouseCurrentRef.current.y += (mouseTargetRef.current.y - mouseCurrentRef.current.y) * 0.06;
        }

        // Calculate reveal progress
        let progress = 1.0;
        if (!prefersReducedMotion) {
          const elapsed = time - startTime;
          if (elapsed <= 0) {
            progress = 0.0;
          } else {
            // Cubic bezier easing (ease-out-cubic: 1 - pow(1 - t, 3))
            const rawProgress = Math.min(elapsed / durationMs, 1.0);
            progress = 1.0 - Math.pow(1.0 - rawProgress, 3.0);
          }
        }

        gl.useProgram(program);
        gl.uniform1f(uProgressLoc, progress);
        gl.uniform2f(uResolutionLoc, canvas.width, canvas.height);
        gl.uniform2f(uOffsetLoc, mouseCurrentRef.current.x, mouseCurrentRef.current.y);

        gl.drawArrays(gl.TRIANGLES, 0, 6);

        animId = requestAnimationFrame(render);
      };

      animId = requestAnimationFrame(render);

      return () => {
        window.removeEventListener("resize", updateSize);
        if (animId) cancelAnimationFrame(animId);
      };
    };

    img.onerror = () => {
      console.warn("Could not load chrome-hands image, using canvas fallback");
      setWebGlFailed(true);
    };

    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [src, durationMs, revealDelayMs, maxDrift]);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full overflow-hidden select-none pointer-events-none ${className}`}
      aria-hidden="true"
    >
      {/* Hidden accessible image for screen readers */}
      <img
        src={src}
        alt={alt}
        className="sr-only"
        aria-hidden="false"
      />

      {/* WebGL Hardware-Accelerated Dither Canvas */}
      {!webGlFailed ? (
        <canvas
          ref={canvasRef}
          className={`w-full h-full block transition-opacity duration-700 ${
            isLoaded ? "opacity-100" : "opacity-0"
          }`}
        />
      ) : (
        /* Fallback if WebGL is unavailable */
        <div className="w-full h-full relative bg-[#0B0B0D] flex items-center justify-center">
          <img
            src={src}
            alt={alt}
            className="w-full h-full object-cover opacity-90 filter contrast-125 brightness-105"
            style={{
              maskImage: "radial-gradient(ellipse at center, rgba(0,0,0,1) 40%, rgba(0,0,0,0) 85%)",
              WebkitMaskImage: "radial-gradient(ellipse at center, rgba(0,0,0,1) 40%, rgba(0,0,0,0) 85%)",
            }}
          />
        </div>
      )}

      {/* Subtle Vignette Gradient overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(11,11,13,0) 20%, rgba(11,11,13,0.65) 75%, rgba(11,11,13,0.95) 100%)",
        }}
      />
    </div>
  );
};

export default DitherReveal;

