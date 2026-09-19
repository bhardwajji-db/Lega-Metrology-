import test from 'node:test';
import assert from 'node:assert/strict';

function setMockEnv({ isSecure, hasMediaDevices, hasGetUserMedia, legacyGUM }) {
  const mockNav = {};
  if (hasMediaDevices) {
    mockNav.mediaDevices = {};
    if (hasGetUserMedia) {
      mockNav.mediaDevices.getUserMedia = async (constraints) => ({
        id: 'mock-stream',
        getTracks: () => []
      });
    }
  }
  if (legacyGUM) {
    mockNav.getUserMedia = legacyGUM;
  }

  const mockWin = {
    isSecureContext: isSecure,
    location: {
      protocol: isSecure ? 'https:' : 'http:',
      hostname: isSecure ? 'localhost' : '192.168.1.100'
    }
  };

  Object.defineProperty(globalThis, 'window', { value: mockWin, configurable: true, writable: true });
  Object.defineProperty(globalThis, 'navigator', { value: mockNav, configurable: true, writable: true });
}

test('Camera Utility Matrix Tests', async (t) => {
  await t.test('1. Insecure Context: window.isSecureContext === false', async () => {
    setMockEnv({ isSecure: false, hasMediaDevices: false });

    const { checkCameraCapability, formatCameraError } = await import('./camera.ts?' + Date.now());
    const res = checkCameraCapability();
    assert.equal(res.supported, false);
    assert.equal(res.isSecure, false);
    assert.equal(res.errorMessage, 'Camera access requires HTTPS or localhost.');

    const errFormatted = formatCameraError(new TypeError("Cannot read properties of undefined (reading 'getUserMedia')"));
    assert.equal(errFormatted, 'Camera access requires HTTPS or localhost.');
  });

  await t.test('2. Missing MediaDevices in Secure Context', async () => {
    setMockEnv({ isSecure: true, hasMediaDevices: false });

    const { checkCameraCapability, formatCameraError } = await import('./camera.ts?' + (Date.now() + 1));
    const res = checkCameraCapability();
    assert.equal(res.supported, false);
    assert.equal(res.isSecure, true);
    assert.equal(res.errorMessage, 'Camera access is not supported in this environment.');

    const errFormatted = formatCameraError(new TypeError("Cannot read properties of undefined (reading 'getUserMedia')"));
    assert.equal(errFormatted, 'Camera access is not supported in this environment.');
  });

  await t.test('3. Permission Denied (NotAllowedError)', async () => {
    const { formatCameraError } = await import('./camera.ts?' + (Date.now() + 2));
    const err = new Error('Permission denied');
    err.name = 'NotAllowedError';
    assert.equal(
      formatCameraError(err),
      'Camera permission was denied. Please allow camera access and try again.'
    );
  });

  await t.test('4. No Hardware (NotFoundError)', async () => {
    const { formatCameraError } = await import('./camera.ts?' + (Date.now() + 3));
    const err = new Error('Requested device not found');
    err.name = 'NotFoundError';
    assert.equal(
      formatCameraError(err),
      'No camera device was detected.'
    );
  });

  await t.test('5. Camera in use (NotReadableError)', async () => {
    const { formatCameraError } = await import('./camera.ts?' + (Date.now() + 4));
    const err = new Error('Could not start video source');
    err.name = 'NotReadableError';
    assert.equal(
      formatCameraError(err),
      'Camera is already in use by another application or process.'
    );
  });

  await t.test('6. Legacy getUserMedia polyfill shim', async () => {
    let legacyCalled = false;
    setMockEnv({
      isSecure: true,
      hasMediaDevices: false,
      legacyGUM: (constraints, success, error) => {
        legacyCalled = true;
        success({ id: 'legacy-stream', getTracks: () => [] });
      }
    });

    const { ensureMediaDevicesShim, checkCameraCapability } = await import('./camera.ts?' + (Date.now() + 5));
    ensureMediaDevicesShim();
    assert.equal(typeof globalThis.navigator.mediaDevices.getUserMedia, 'function');

    const stream = await globalThis.navigator.mediaDevices.getUserMedia({ video: true });
    assert.equal(legacyCalled, true);
    assert.equal(stream.id, 'legacy-stream');
  });

  await t.test('7. Clean stream stop (stopMediaStream)', async () => {
    let stoppedCount = 0;
    const mockStream = {
      getTracks: () => [
        { stop: () => { stoppedCount++; } },
        { stop: () => { stoppedCount++; } }
      ]
    };

    const { stopMediaStream } = await import('./camera.ts?' + (Date.now() + 6));
    stopMediaStream(mockStream);
    assert.equal(stoppedCount, 2);
  });

  await t.test('8. Full Success: Secure Context + MediaDevices + getUserMedia', async () => {
    setMockEnv({ isSecure: true, hasMediaDevices: true, hasGetUserMedia: true });
    const { checkCameraCapability, requestCameraStream } = await import('./camera.ts?' + (Date.now() + 7));
    const res = checkCameraCapability();
    assert.equal(res.supported, true);
    assert.equal(res.isSecure, true);
    assert.equal(res.hasGetUserMedia, true);
    assert.equal(res.errorMessage, null);

    const stream = await requestCameraStream({ facingMode: 'environment' });
    assert.equal(stream.id, 'mock-stream');
  });
});
