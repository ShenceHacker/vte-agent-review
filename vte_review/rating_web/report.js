/* Presentation only: preserve the report's wording and order. */
"use strict";
window.VTEReport = {
  render(text) {
    const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    return String(text ?? '').split(/\r?\n\s*\r?\n/).filter(part => part.trim()).map(part => {
      const match = part.match(/^(当前判断|与上次相比的变化|建议措施|依据与适用条件|治疗建议|监测与随访|随访计划|注意事项|Current assessment|Changes since previous visit|Recommended actions|Rationale and conditions)[：:]/i);
      const title = match ? match[0] : '';
      const body = part.slice(title.length);
      const parts = typeof Intl.Segmenter === 'function'
        ? Array.from(new Intl.Segmenter(undefined, {granularity:'sentence'}).segment(body), item => item.segment)
        : body.split(/(?<=[。！？])(?=\S)/);
      const sentences = parts.map(sentence => '<span class="clinical-sentence">'+escape(sentence)+'</span>').join('');
      return '<section class="clinical-block">'+(title ? '<h3>'+escape(title)+'</h3>' : '')+'<div class="clinical-text">'+sentences+'</div></section>';
    }).join('');
  }
};
