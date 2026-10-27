import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchAuthenticatedBlob } from '../src/utils/authenticatedFiles.js';

test('authenticated files use headers, reject redirects and never put credentials in the URL', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://arl.example/api/image/task/file.jpg');
    assert.deepEqual(options.headers, { Token: 'fixture-token' });
    assert.equal(options.redirect, 'error');
    return new Response(new Blob(['image'], { type: 'image/jpeg' }));
  });
  globalThis.window = { location: { origin: 'https://arl.example' } };
  globalThis.localStorage = { getItem: () => 'fixture-token' };
  const blob = await fetchAuthenticatedBlob('/api/image/task/file.jpg');
  assert.equal(await blob.text(), 'image');
});

test('external resource URLs cannot receive the account token', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new Error('must not fetch'); });
  await assert.rejects(fetchAuthenticatedBlob('https://other.example/api/image/x'), /Invalid/);
  await assert.rejects(fetchAuthenticatedBlob('//other.example/api/image/x'), /Invalid/);
  assert.equal(fetch.mock.callCount(), 0);
});

test('expired sessions and JSON error bodies are never converted into downloadable files', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('{}', { status: 401 }));
  await assert.rejects(fetchAuthenticatedBlob('/api/image/task/file.jpg'), /401/);
  globalThis.fetch = async () => Response.json({ code: 401, message: 'not login' });
  await assert.rejects(fetchAuthenticatedBlob('/api/image/task/file.jpg'), /not login/);
});
