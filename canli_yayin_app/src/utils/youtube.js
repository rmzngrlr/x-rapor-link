export const extractVideoId = (url) => {
  if (!url) return null;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);

  if (match && match[2].length === 11) {
    return match[2];
  }

  if (url.includes('/live/')) {
    const parts = url.split('/live/');
    if (parts.length > 1) {
      const potentialId = parts[1].split(/[?&]/)[0];
      if (potentialId.length === 11) {
        return potentialId;
      }
    }
  }

  if (url.length === 11 && /^[a-zA-Z0-9_-]{11}$/.test(url)) {
    return url;
  }

  return null;
};

export const getEmbedUrl = (videoId) => {
  const origin = window.location.origin;
  return `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=1&origin=${origin}`;
};
