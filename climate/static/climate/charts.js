/* Shared Highcharts theming that follows the site's light/dark tokens. */
window.ES = (function(){
  var css = function(n){ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
  function palette(){
    return {ink: css('--ink'), soft: css('--ink-soft'), faint: css('--ink-faint'), line: css('--line-soft'), grid: css('--line'),
            paper: css('--paper-raised'), teal: css('--teal-500'), deep: css('--teal-700'), amber: css('--amber-500'),
            hot: css('--coral-600'), cool: css('--cool'), green: css('--green-600')};
  }
  function apply(){
    var P = palette();
    Highcharts.setOptions({
      chart: {backgroundColor: 'transparent', style: {fontFamily: 'Inter, sans-serif'}, animation: {duration: 450}},
      title: {text: null}, credits: {enabled: false},
      colors: [P.hot, P.cool, P.amber, P.teal, P.green, P.deep],
      xAxis: {lineColor: P.grid, tickColor: P.grid, labels: {style: {color: P.faint}}, title: {style: {color: P.faint}}},
      yAxis: {gridLineColor: P.line, labels: {style: {color: P.faint}}, title: {style: {color: P.faint}}},
      legend: {itemStyle: {color: P.soft, fontWeight: '500'}, itemHoverStyle: {color: P.ink}},
      tooltip: {backgroundColor: P.paper, borderColor: P.grid, style: {color: P.ink}, shared: true},
      plotOptions: {series: {animation: {duration: 450}}},
      exporting: {buttons: {contextButton: {symbolStroke: P.faint, theme: {fill: 'transparent'}}}}
    });
    return P;
  }
  var listeners = [];
  document.addEventListener('themechange', function(){ apply(); listeners.forEach(function(f){ f(); }); });
  return {palette: palette, apply: apply, onTheme: function(f){ listeners.push(f); }};
})();
