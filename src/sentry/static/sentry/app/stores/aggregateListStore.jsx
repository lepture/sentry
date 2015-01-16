/** @jsx React.DOM */

var Reflux = require("reflux");

var alertActions = require("../actions/alertActions");
var aggregateListActions = require('../actions/aggregateListActions');
var utils = require("../utils");

var ERR_CHANGE_ASSIGNEE = 'Unable to change assignee. Please try again.';

var aggregateListStore = Reflux.createStore({
  listenables: aggregateListActions,

  init: function() {
    // TODO(dcramer): what we want to actually do is keep this as a simple
    // list and have stream add/remove items as they're modified within stream
    // itself
    this.items = new utils.Collection([], {
      equals: function(self, other) {
        return self.id === other.id;
      },
      limit: 50
    });
  },

  // TODO(dcramer): this should actually come from an action of some sorts
  loadInitialData: function(items) {
    this.items.empty();
    this.items.push(items);
    this.trigger(this.items, 'initial');
  },

  onSetAssignedTo: function(itemId, userEmail) {
    $.ajax({
      url: '/api/0/groups/' + itemId + '/',
      method: 'PUT',
      data: JSON.stringify({
        assignedTo: userEmail
      }),
      contentType: 'application/json',
      success: function(data){
        this.items.update(data);
        this.trigger(this.items, 'assignedTo', itemId, userEmail);
      }.bind(this),
      error: function(){
        alertActions.addAlert(ERR_CHANGE_ASSIGNEE, 'error');
      }.bind(this)
    });
  }
});

module.exports = aggregateListStore;
