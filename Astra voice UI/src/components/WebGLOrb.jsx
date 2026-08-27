import React, { useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';

export const WebGLOrb = ({ size = 280, interactive = true, className = '' }) => {
  const canvasRef = useRef(null);
  const { assistantState, audioLevel, settings } = useApp();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let animId;
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) return;

    // Compile Vertex and Fragment Shaders
    const vsSource = `
      attribute vec2 a_position;
      varying vec2 v_texCoord;
      void main() {
        v_texCoord = a_position * 0.5 + 0.5;
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `;

    const fsSource = `
      precision highp float;
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform vec2 u_mouse;
      uniform float u_audio;
      uniform float u_state; // 0=idle, 1=listening, 2=thinking, 3=speaking
      uniform vec3 u_color;
      varying vec2 v_texCoord;

      // Simplex-like 2D noise helper
      float hash(vec2 p) {
        return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
      }

      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        vec2 u = f*f*(3.0-2.0*f);
        return mix(mix(hash(i + vec2(0.0,0.0)), hash(i + vec2(1.0,0.0)), u.x),
                   mix(hash(i + vec2(0.0,1.0)), hash(i + vec2(1.0,1.0)), u.x), u.y);
      }

      void main() {
        vec2 uv = v_texCoord;
        vec2 center = vec2(0.5);

        // Slight pull toward mouse when hovered
        vec2 mouseOffset = (u_mouse - vec2(0.5)) * 0.08;
        vec2 pos = uv - (center + mouseOffset);
        float d = length(pos);

        // State-based speed and pulse
        float speed = 1.8;
        float basePulse = 0.45;
        float audioReaction = u_audio * 0.25;

        if (u_state > 0.5 && u_state < 1.5) { // Listening
          speed = 3.5;
          basePulse = 0.52 + audioReaction;
        } else if (u_state >= 1.5 && u_state < 2.5) { // Thinking
          speed = 4.8;
          basePulse = 0.48;
        } else if (u_state >= 2.5) { // Speaking
          speed = 3.2;
          basePulse = 0.55 + audioReaction * 1.2;
        }

        float pulse = basePulse + 0.08 * sin(u_time * speed);
        float glow = 0.065 / max(d * (1.1 - pulse), 0.001);

        // Organic multi-layer fluid turbulence
        float angle = atan(pos.y, pos.x);
        float n1 = noise(vec2(cos(angle * 3.0 + u_time * 1.5), sin(angle * 3.0 - u_time * 1.5)) * 2.0);
        float n2 = sin(pos.x * 24.0 + u_time * speed) * (0.02 + audioReaction * 0.08);
        
        float distToOrb = d + (n1 * 0.04 + n2);

        // Vibrant Astra Violet / Custom Color
        vec3 col = u_color;
        
        // Inner highlights
        if (u_state >= 1.5 && u_state < 2.5) {
          // Shifting tones for thinking
          col = mix(u_color, vec3(0.81, 0.74, 1.0), 0.5 + 0.5 * sin(u_time * 3.0));
        } else if (u_state >= 2.5) {
          // Warm glowing center for speaking
          col = mix(u_color, vec3(0.9, 0.85, 1.0), 0.3 + 0.3 * sin(u_time * 4.0));
        }

        float alpha = smoothstep(0.42, 0.08, distToOrb);
        
        // Outer subtle corona glow
        float outerGlow = smoothstep(0.5, 0.1, d) * (0.4 + audioReaction);
        
        vec3 finalColor = col * (glow * 1.1 + outerGlow * 0.5);
        gl_FragColor = vec4(finalColor, clamp(alpha * glow * 1.3, 0.0, 1.0));
      }
    `;

    const createShader = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.error('Shader compilation error:', gl.getShaderInfoLog(s));
        gl.deleteShader(s);
        return null;
      }
      return s;
    };

    const vs = createShader(gl.VERTEX_SHADER, vsSource);
    const fs = createShader(gl.FRAGMENT_SHADER, fsSource);
    if (!vs || !fs) return;

    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);

    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(prog));
      return;
    }

    gl.useProgram(prog);

    // Quad Buffer
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    const pos = gl.getAttribLocation(prog, 'a_position');
    gl.enableVertexAttribArray(pos);
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

    // Uniform Locations
    const uTime = gl.getUniformLocation(prog, 'u_time');
    const uRes = gl.getUniformLocation(prog, 'u_resolution');
    const uMouse = gl.getUniformLocation(prog, 'u_mouse');
    const uAudio = gl.getUniformLocation(prog, 'u_audio');
    const uState = gl.getUniformLocation(prog, 'u_state');
    const uColor = gl.getUniformLocation(prog, 'u_color');

    // Convert hex color to RGB normalized
    const hexToRgb = (hex) => {
      const result = /^#?([a-fd]{2})([a-fd]{2})([a-fd]{2})$/i.exec(hex || '#7c5cfc');
      return result
        ? [parseInt(result[1], 16) / 255, parseInt(result[2], 16) / 255, parseInt(result[3], 16) / 255]
        : [0.486, 0.361, 0.988];
    };

    let mousePos = { x: 0.5, y: 0.5 };
    const handleMouseMove = (e) => {
      if (!interactive) return;
      const rect = canvas.getBoundingClientRect();
      if (rect.width && rect.height) {
        mousePos.x = (e.clientX - rect.left) / rect.width;
        mousePos.y = 1.0 - (e.clientY - rect.top) / rect.height;
      }
    };

    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove);
    }

    // Enable Blending for silky smooth transparency
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    let stateVal = 0;
    if (assistantState === 'listening') stateVal = 1;
    else if (assistantState === 'thinking') stateVal = 2;
    else if (assistantState === 'speaking') stateVal = 3;

    const rgb = hexToRgb(settings?.orbColor);

    const render = (t) => {
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const displayWidth = Math.floor(canvas.clientWidth * dpr);
      const displayHeight = Math.floor(canvas.clientHeight * dpr);

      if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
        canvas.width = displayWidth;
        canvas.height = displayHeight;
      }

      gl.viewport(0, 0, canvas.width, canvas.height);

      if (uTime) gl.uniform1f(uTime, t * 0.001);
      if (uRes) gl.uniform2f(uRes, canvas.width, canvas.height);
      if (uMouse) gl.uniform2f(uMouse, mousePos.x, mousePos.y);
      if (uAudio) gl.uniform1f(uAudio, audioLevel || 0);
      if (uState) gl.uniform1f(uState, stateVal);
      if (uColor) gl.uniform3f(uColor, rgb[0], rgb[1], rgb[2]);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      if (animId) cancelAnimationFrame(animId);
      if (interactive) {
        window.removeEventListener('mousemove', handleMouseMove);
      }
    };
  }, [assistantState, audioLevel, settings?.orbColor, interactive]);

  return (
    <div
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{ width: size, height: size }}
    >
      <canvas
        ref={canvasRef}
        className="w-full h-full block rounded-full"
        style={{ width: size, height: size }}
      />
    </div>
  );
};
