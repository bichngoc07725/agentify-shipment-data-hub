import { useEffect, useState } from 'react';
import { getToken } from './authStorage';

/** Turns an API file URL (`/api/v1/attachments/{id}/file`) into a blob: URL
 * usable by `<img src>` / `<a href>`.
 *
 * That endpoint is gated by `require_permission("shipping_document", "view")`,
 * and a plain `<img src>` never sends the `Authorization` header — so the
 * browser would get a 401. Fetching here attaches the bearer token and hands
 * back an object URL instead.
 */
export function useAuthedFile(url: string | null | undefined): string | null {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setObjectUrl(null);
      return;
    }

    let revoked = false;
    let created: string | null = null;
    const token = getToken();

    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(res => (res.ok ? res.blob() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(blob => {
        if (revoked) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      })
      .catch(() => setObjectUrl(null));

    return () => {
      revoked = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url]);

  return objectUrl;
}
