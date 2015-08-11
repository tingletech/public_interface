/*global _*/
/*global QueryManager */
/*global GlobalSearchForm */
/*global FacetForm */
/*global CarouselContext */

'use strict'; 

if(typeof console === 'undefined') {
  console = { log: function() { } };
}

$(document).on('pjax:timeout', function() { return false; });

var qm, globalSearchForm, facetForm, carousel, DESKTOP;

$(document).ready(function() {
  $('html').removeClass('no-jquery');
  $.pjax.defaults.timeout = 5000;
  $(document).pjax('a[data-pjax=js-pageContent]', '#js-pageContent');
  
	if ($(window).width() > 900) {
		DESKTOP = true;
	} else {
		DESKTOP = false;
	}

  $(document).on('pjax:beforeReplace', '#js-pageContent', function() {
    if($('#js-mosaicContainer').length > 0) {
      $('#js-mosaicContainer').infinitescroll('destroy');
    }
    if(carousel !== undefined) {
      carousel = undefined;
    }
  });

  $(document).on('pjax:end', '#js-pageContent', function() {
    //if we've gotten to a page without search context, clear the query manager
    if($('#js-facet').length <= 0 && $('#js-objectViewport').length <= 0) {
      qm.clear({silent: true});        
    }
    
    if($('#js-facet').length > 0) {
      if (facetForm === undefined) {
        facetForm = new FacetForm({model: qm});
      }
      facetForm.toggleSelectDeselectAll();

      // get rid of any visible tooltips
      var visibleTooltips = $('[data-toggle="tooltip"][aria-describedby]');
      for (var i=0; i<visibleTooltips.length; i++) {
        var tooltipId = $(visibleTooltips[i]).attr('aria-describedby');
        $('#' + tooltipId).remove();
      }
      // reinit tooltips
      $('[data-toggle="tooltip"]').tooltip({
        placement: 'top'
      });
    }
    
    if($('#js-carouselContainer').length > 0 && carousel === undefined) {
      carousel = new CarouselContext({model: qm});
    }
    
    //if we've gotten to a page with a list of collection mosaics, init infinite scroll
    if($('#js-mosaicContainer').length > 0) {
      $('#js-mosaicContainer').infinitescroll({
        navSelector: '#js-collectionPagination',
        nextSelector: '#js-collectionPagination a.js-next',
        itemSelector: '#js-mosaicContainer div.js-collectionMosaic',
        debug: false,
        loading: {
          finishedMsg: 'All collections showing.',
          img: 'http://localhost:9000/images/orange-spinner.gif',
          msgText: '',
          selector: '#js-loading'
        }
      });
    }
  });
  
  qm = new QueryManager();
  globalSearchForm = new GlobalSearchForm({model: qm});
  
  if($('#js-facet').length > 0) {
    facetForm = new FacetForm({model: qm});
    facetForm.toggleSelectDeselectAll();
    $('[data-toggle="tooltip"]').tooltip({
      placement: 'top'
    });
  }
  
  if($('#js-carouselContainer').length > 0 && carousel === undefined) {
    carousel = new CarouselContext({model: qm});
  }
  
  $('#js-global-header-logo').on('click', function() {
    if (!_.isEmpty(qm.attributes) || !_.isEmpty(sessionStorage)) {
      qm.clear();
    }
  });
  
});

if(!('backgroundBlendMode' in document.body.style)) {
    // No support for background-blend-mode
  var html = document.getElementsByTagName('html')[0];
  html.className = html.className + ' no-background-blend-mode';
}
