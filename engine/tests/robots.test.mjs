// node robots.test.mjs — robots.txt matching. A '/*/x' rule once blocked whole sites.
import { robotsRule } from '../robots.mjs';
const cases = [
  ['/*/media/oembed', '/', false], ['/*/media/oembed', '/en/media/oembed', true], ['/admin/', '/admin/users', true],
  ['/admin/', '/administration', false], ['/*.pdf$', '/files/a.pdf', true], ['/*.pdf$', '/files/a.pdf?x=1', false],
  ['/search?q=', '/search?q=parks', true], ['/', '/anything', true],
];
let bad = 0;
for (const [rule, path, want] of cases) {
  const got = robotsRule(rule).test(path);
  if (got !== want) { bad++; console.error(`FAIL ${rule} vs ${path}: got ${got}, want ${want}`); }
}
console.log(bad ? `${bad} failed` : `robots rules: ${cases.length} passed`);
process.exit(bad ? 1 : 0);
