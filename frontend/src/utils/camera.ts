/**
 * MetrCheck AI — Robust Camera & MediaDevices Utility
 * 
 * Provides defense-in-depth capability detection, legacy WebRTC polyfills,
 * progressive constraint fallbacks, clean stream lifecycle management,
 * and user-friendly error formatting across Web and Capacitor Android environments.
 */

export interface CameraCapabilityResult {
  supported: boolean;
  isSecure: boolean;
  hasNavigator: boolean;
  hasMediaDevices: boolean;
  hasGetUserMedia: boolean;
  errorMessage: string | null;
  errorReason: 'INSECURE_CONTEXT' | 'UNSUPPORTED_BROWSER' | 'NO_DEVICES' | null;
}

export interface RequestCameraOptions {
  facingMode?: 'environment' | 'user';
  idealWidth?: number;
  idealHeight?: number;
}

/**
 * Checks whether the current runtime environment is a W3C Secure Context.
 * Modern browsers strictly restrict navigator.mediaDevices to Secure Contexts
 * (https://, localhost, 127.0.0.1, or packaged app schemes like capacitor://).
 */
export function isSecureContext(): boolean {
  if (typeof window === 'undefined') return false;
  if (typeof window.isSecureContext === 'boolean') {
    return window.isSecureContext;
  }
  const proto = window.location.protocol;
  const host = window.location.hostname;
  return proto === 'https:' || host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

/**
 * Ensures legacy WebRTC implementations (navigator.getUserMedia / webkitGetUserMedia / mozGetUserMedia)
 * are adapted to the standard Promise-based navigator.mediaDevices.getUserMedia interface.
 */
export function ensureMediaDevicesShim(): void {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return;

  const nav = navigator as any;
  if (nav.mediaDevices === undefined) {
    nav.mediaDevices = {};
  }

  if (nav.mediaDevices.getUserMedia === undefined) {
    const legacyGUM = nav.getUserMedia || nav.webkitGetUserMedia || nav.mozGetUserMedia || nav.msGetUserMedia;
    if (legacyGUM) {
      nav.mediaDevices.getUserMedia = function (constraints: MediaStreamConstraints): Promise<MediaStream> {
        return new Promise<MediaStream>((resolve, reject) => {
          legacyGUM.call(nav, constraints, resolve, reject);
        });
      };
    }
  }
}

/**
 * Evaluates browser and device camera capability before attempting hardware access.
 */
export function checkCameraCapability(): CameraCapabilityResult {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return {
      supported: false,
      isSecure: false,
      hasNavigator: false,
      hasMediaDevices: false,
      hasGetUserMedia: false,
      errorMessage: 'Camera access is not supported in this environment.',
      errorReason: 'UNSUPPORTED_BROWSER'
    };
  }

  const secure = isSecureContext();
  if (!secure) {
    return {
      supported: false,
      isSecure: false,
      hasNavigator: true,
      hasMediaDevices: Boolean(navigator.mediaDevices),
      hasGetUserMedia: Boolean(navigator.mediaDevices?.getUserMedia),
      errorMessage: 'Camera access requires HTTPS or localhost.',
      errorReason: 'INSECURE_CONTEXT'
    };
  }

  ensureMediaDevicesShim();

  const hasMediaDevices = Boolean(navigator.mediaDevices);
  const hasGetUserMedia = Boolean(navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function');

  if (!hasMediaDevices || !hasGetUserMedia) {
    return {
      supported: false,
      isSecure: secure,
      hasNavigator: true,
      hasMediaDevices,
      hasGetUserMedia,
      errorMessage: 'Camera access is not supported in this environment.',
      errorReason: 'UNSUPPORTED_BROWSER'
    };
  }

  return {
    supported: true,
    isSecure: true,
    hasNavigator: true,
    hasMediaDevices: true,
    hasGetUserMedia: true,
    errorMessage: null,
    errorReason: null
  };
}

/**
 * Maps raw JavaScript errors and DOMExceptions into clear, actionable user messages.
 */
export function formatCameraError(err: any): string {
  if (!err) return 'Unable to start the camera. Please retry.';
  if (typeof err === 'string') return err;

  const name = err.name || '';
  const msg = (err.message || '').toString();

  // Security or Insecure context
  if (name === 'SecurityError' || msg.toLowerCase().includes('secure') || (!isSecureContext() && msg.includes('getUserMedia'))) {
    return 'Camera access requires HTTPS or localhost.';
  }

  // Permission denied or dismissed
  if (
    name === 'NotAllowedError' ||
    name === 'PermissionDeniedError' ||
    name === 'PermissionDismissedError' ||
    msg.toLowerCase().includes('permission') ||
    msg.toLowerCase().includes('denied')
  ) {
    return 'Camera permission was denied. Please allow camera access and try again.';
  }

  // Device not found / hardware missing
  if (
    name === 'NotFoundError' ||
    name === 'DevicesNotFoundError' ||
    msg.toLowerCase().includes('not found') ||
    msg.toLowerCase().includes('no camera')
  ) {
    return 'No camera device was detected.';
  }

  // Device already open by another process
  if (
    name === 'NotReadableError' ||
    name === 'TrackStartError' ||
    msg.toLowerCase().includes('in use') ||
    msg.toLowerCase().includes('already allocated')
  ) {
    return 'Camera is already in use by another application or process.';
  }

  // Constraint not satisfied
  if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
    return 'Camera does not support requested resolution or angle.';
  }

  // Operation aborted
  if (name === 'AbortError') {
    return 'Camera initialization was interrupted. Please retry.';
  }

  // TypeError (e.g. Cannot read properties of undefined reading getUserMedia)
  if (name === 'TypeError' && (msg.includes('getUserMedia') || msg.includes('undefined'))) {
    if (!isSecureContext()) {
      return 'Camera access requires HTTPS or localhost.';
    }
    return 'Camera access is not supported in this environment.';
  }

  return 'Unable to start the camera. Please retry.';
}

/**
 * Safely requests a camera video stream with progressive fallback constraints.
 * If ideal high-resolution or environment facingMode fails, automatically retries
 * with relaxed constraints to guarantee hardware compatibility across webcams.
 */
export async function requestCameraStream(options: RequestCameraOptions = {}): Promise<MediaStream> {
  const capability = checkCameraCapability();
  if (!capability.supported) {
    throw new Error(capability.errorMessage || 'Camera access is not supported in this environment.');
  }

  const mode = options.facingMode || 'environment';
  const width = options.idealWidth || 1280;
  const height = options.idealHeight || 720;

  // Level 1: Preferred ideal resolution + facing mode
  const primaryConstraints: MediaStreamConstraints = {
    audio: false,
    video: {
      facingMode: { ideal: mode },
      width: { ideal: width },
      height: { ideal: height }
    }
  };

  try {
    return await navigator.mediaDevices.getUserMedia(primaryConstraints);
  } catch (err: any) {
    console.warn('[Camera] Primary camera constraints failed:', err);

    // If constraint failed (e.g. facingMode not supported by external USB webcam),
    // progressively attempt fallback constraints before reporting error
    const isConstraintError = 
      err?.name === 'OverconstrainedError' || 
      err?.name === 'ConstraintNotSatisfiedError' ||
      err?.name === 'TypeError';

    if (isConstraintError || err?.name === 'NotFoundError') {
      try {
        // Fallback 1: Simple facingMode
        return await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: mode }
        });
      } catch (fallback1Err) {
        console.warn('[Camera] Fallback 1 failed, trying unconstrained video:', fallback1Err);
        // Fallback 2: Any available video stream
        try {
          return await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: true
          });
        } catch (fallback2Err) {
          throw new Error(formatCameraError(fallback2Err));
        }
      }
    }

    throw new Error(formatCameraError(err));
  }
}

/**
 * Safely stops all tracks on a MediaStream to release camera hardware immediately.
 */
export function stopMediaStream(stream: MediaStream | null): void {
  if (!stream) return;
  try {
    const tracks = stream.getTracks();
    tracks.forEach(track => {
      try {
        track.stop();
      } catch (e) {
        // track stop error ignored
      }
    });
  } catch (e) {
    console.warn('[Camera] Error stopping stream tracks:', e);
  }
}
