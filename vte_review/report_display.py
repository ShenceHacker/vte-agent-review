"""Use the same lossless report layout in offline HTML and the rating portal."""
from pathlib import Path
import re


def enhance_report_html(page):
    page = re.sub(r'<!-- vte-reader-layout:start -->.*?<!-- vte-reader-layout:end -->', '', page, flags=re.S)
    assets = Path(__file__).with_name('rating_web')
    css = (assets / 'report.css').read_text(encoding='utf-8')
    js = (assets / 'report.js').read_text(encoding='utf-8')
    script = js + '''
function renderVisibleReports(root) {
  root.querySelectorAll('.answer:not([data-rendered]), .original:not([data-rendered])').forEach(element => {
    for(let parent=element.parentElement;parent;parent=parent.parentElement) {
      if(parent.tagName==='DETAILS'&&!parent.open)return;
    }
    const original=element.textContent;
    element.dataset.rendered='true';element.classList.add('clinical-report');
    element.innerHTML=window.VTEReport.render(original);
  });
}
renderVisibleReports(document);
document.addEventListener('toggle',event=>{
  if(event.target.tagName==='DETAILS'&&event.target.open)renderVisibleReports(event.target);
},true);
document.querySelectorAll('table:not(.record-table)').forEach(table => {
  if (table.parentElement.classList.contains('vte-table-scroll')) return;
  const wrapper = document.createElement('div');
  wrapper.className = 'vte-table-scroll';
  table.before(wrapper); wrapper.appendChild(table);
});
'''
    layout = '<!-- vte-reader-layout:start --><style>'+css+'</style><script>'+script+'</script><!-- vte-reader-layout:end -->'
    return page.replace('</html>', layout+'</html>')
