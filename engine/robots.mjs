// robots.txt path rules: prefix match, '*' = any run of characters, a trailing '$' = end of URL.
export function robotsRule(rule) {
  const anchored = rule.endsWith('$');
  const body = (anchored ? rule.slice(0, -1) : rule)
    .split('*')
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('.*');
  return new RegExp('^' + body + (anchored ? '$' : ''));
}
export const isBlocked = (url, disallow) => {
  const u = new URL(url);
  return disallow.some((d) => robotsRule(d).test(u.pathname + u.search));
};
