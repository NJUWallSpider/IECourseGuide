/* 全站右下角「投稿 / 纠错」悬浮入口。
 *
 * 依赖 overrides/main.html 注入的 window.IE_CONTRIB：
 *   { repo: "NJUWallSpider/IECourseGuide", siteRoot: "提交修改/" }
 * 其中 siteRoot 是 MkDocs 的 url 过滤器按当前页面生成的相对路径，
 * 因此子路径部署（如 /IECourseGuide/）也能正确跳转。
 *
 * 纯原生 JS，无第三方依赖；在「提交修改」页自身不显示。
 */
(function () {
  'use strict';

  var CONTRIB_PAGE = '提交修改';
  var COURSE_SECTIONS = ['专业核心课', '专业选修课', '跨专业课', '数理基础课', '必学工具'];

  function normalizePath(path) {
    var value = String(path || '').replace(/\\/g, '/');
    try {
      // 浏览器通常把中文路径 percent-encode，先解码再比较
      return decodeURIComponent(value);
    } catch (error) {
      return value;
    }
  }

  function isContributionPage() {
    var path = normalizePath(window.location.pathname);
    // /提交修改/、/提交修改/index.html、以及结尾没有斜杠的情况
    return (
      path.indexOf('/' + CONTRIB_PAGE + '/') !== -1 ||
      path === '/' + CONTRIB_PAGE ||
      path.slice(-('' + '/' + CONTRIB_PAGE).length) === '/' + CONTRIB_PAGE
    );
  }

  function isCoursePage() {
    var path = normalizePath(window.location.pathname);
    for (var i = 0; i < COURSE_SECTIONS.length; i++) {
      if (path.indexOf('/' + COURSE_SECTIONS[i] + '/') !== -1) {
        return true;
      }
    }
    return false;
  }

  function currentPath() {
    // location.pathname 通常是 percent-encode 过的，先解码，稍后再编码一次，
    // 避免 ?from= 出现双重编码导致投稿页无法匹配课程。
    var path = String(window.location.pathname || '').replace(/\\/g, '/');
    try {
      return decodeURIComponent(path);
    } catch (error) {
      return path;
    }
  }

  function findNavHref() {
    // 兜底：直接复用左侧导航里「提交修改」链接的 href（MkDocs 已经算好相对路径）
    var links = document.querySelectorAll('.md-nav a[href]');
    for (var i = 0; i < links.length; i++) {
      var text = (links[i].textContent || '').trim();
      if (text === CONTRIB_PAGE) {
        return links[i].getAttribute('href');
      }
    }
    return '';
  }

  function buildHref() {
    var config = window.IE_CONTRIB || {};
    var href = config.siteRoot || findNavHref();
    if (!href) {
      // 最后兜底：按当前页面深度拼相对路径无法保证正确，只能退化为站内绝对路径
      href = '/' + encodeURI(CONTRIB_PAGE) + '/';
    }
    // 课程页带上来源路径，投稿页可据此自动预选课程
    if (isCoursePage()) {
      href += (href.indexOf('?') === -1 ? '?' : '&') + 'from=' + encodeURIComponent(currentPath());
    }
    return href;
  }

  function createButton() {
    var link = document.createElement('a');
    link.className = 'ie-fab';
    link.href = buildHref();
    link.title = '投稿 / 纠错：无需 fork、无需懂 git';
    link.setAttribute('aria-label', '投稿 / 纠错');

    var icon = document.createElement('span');
    icon.className = 'ie-fab-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '✍️';

    var text = document.createElement('span');
    text.className = 'ie-fab-text';
    text.textContent = '投稿 / 纠错';

    link.appendChild(icon);
    link.appendChild(text);
    return link;
  }

  function watchComments(button) {
    // 滚动到 Giscus 评论区附近时隐藏悬浮按钮，避免挡住评论。
    // comments.html 里的 Giscus 脚本会创建 iframe.giscus-frame 并异步加载，
    // 所以先等它出现，再用 IntersectionObserver 监听它是否进入视口。
    if (!('IntersectionObserver' in window)) {
      return;
    }

    function attach(frame) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            button.classList.toggle('ie-fab--hidden', entry.isIntersecting);
          });
        },
        { rootMargin: '0px 0px 96px 0px', threshold: 0 }
      );
      observer.observe(frame);
    }

    var existing = document.querySelector('iframe.giscus-frame');
    if (existing) {
      attach(existing);
      return;
    }

    if (!('MutationObserver' in window)) {
      return;
    }
    var mutationObserver = new MutationObserver(function () {
      var frame = document.querySelector('iframe.giscus-frame');
      if (frame) {
        mutationObserver.disconnect();
        attach(frame);
      }
    });
    mutationObserver.observe(document.body, { childList: true, subtree: true });
    // 评论区没加载（离线 / 被拦截 / 无评论）时不必一直监听
    window.setTimeout(function () {
      mutationObserver.disconnect();
    }, 15000);
  }

  function init() {
    if (isContributionPage()) {
      return;
    }
    if (document.querySelector('.ie-fab')) {
      return;
    }
    var button = createButton();
    // 等 Material 的 instant loading 替换完 body 再插入（这里用 body 直接追加即可）
    document.body.appendChild(button);
    watchComments(button);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
