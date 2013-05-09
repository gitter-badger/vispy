""" 
The event modules implements the classes that make up the event system.
The Event class and its subclasses are used to represent "stuff that happens".
The EventEmitter class provides an interface to connect to events and
to emit events. The EmitterGroup groups EventEmitter objects.

For more information see http://github.com/vispy/vispy/wiki/API_Events

"""


import collections, inspect

# todo: we want Events to be light and fast, so that performance  is not degraded too much with move events.
# todo: use __slots__ (at least on the event classes where it matters)

class Event(object):
    """Class describing events that occur and can be reacted to with callbacks.
    Each event instance contains information about a single event that has
    occurred such as a key press, mouse motion, timer activation, etc.
    
    Subclasses: :class:`KeyEvent`, :class:`MouseEvent`, :class:`TouchEvent`, 
    :class:`StylusEvent`
    
    The creation of events and passing of events to the appropriate callback
    functions in the responsibility of :class:`EventEmitter` instances.
    
    Input arguments
    ---------------
    type : str
       string indicating the event type (e.g. mouse_press, key_release)
    kwds : keyword arguments
        Any additional keyword arguments are stored as attributes on the event.
    
    """
    def __init__(self, type, **kwds):
        # stack of all sources this event has been emitted through
        self._sources = [] 
        # string indicating the event type (mouse_press, key_release, etc.)
        self._type = type
        self._handled = False
        self._blocked = False
        self.__dict__.update(kwds)
        
    @property
    def source(self):
        """ The object that the event applies to (i.e. the source of the event).
        """
        return self._sources[-1] if self._sources else None
    
    @property
    def sources(self):
        """ List of objects that the event applies to (i.e. are or have
        been a source of the event). Can contain multiple objects in case
        the event traverses a hierarchy of objects.
        """
        return self._sources
    
    def _push_source(self, source):
        self._sources.append(source)
        
    def _pop_source(self):
        return self._sources.pop()
        
    @property
    def type(self):
        """ A string that specifies the type of the event.
        """
        return self._type
        
    @property
    def handled(self):
        """This boolean property indicates whether the event has already been 
        acted on by an event handler. Since many handlers may have access to the 
        same events, it is recommended that each check whether the event has 
        already been handled as well as set handled=True if it decides to 
        act on the event. 
        """
        return self._handled
    
    @handled.setter
    def handled(self, val):
        self._handled = bool(val)
        
    @property
    def blocked(self):
        """This boolean property indicates whether the event will be delivered
        to event callbacks. If it is set to True, then no further callbacks
        will receive the event. When possible, it is recommended to use
        Event.handled rather than Event.blocked.
        """
        return self._blocked
    
    @blocked.setter
    def blocked(self, val):
        self._blocked = bool(val)
    
    def __repr__(self):
        attrs = " ".join(["%s=%s" % pair for pair in self.__dict__.items()])
        return "<%s %s>" % (self.__class__.__name__, attrs)



class MouseEvent(Event):
    """ Class describing mouse events.
    
    Input arguments
    ---------------
    type : str
        string indicating the event type (e.g. mouse_press, key_release)
    pos : (x, y)
        The position of the mouse (in screen coordinates).
    button : int (optional)
        The button that this event applies to.
    modifiers : sequence of ints (optional)
        Which modifier keys were pressed down at the time of the event
        (shift, control, alt).
    kwds : keyword arguments
        Any additional keyword arguments are stored as attributes on the event.
        
    """
    
    def __init__(self, type, pos=None, button=None, modifiers=None, delta=0):
        Event.__init__(self, type)
        self._pos = (0,0) if (pos is None) else (pos[0], pos[1])
        self._button = int(button) if (button is not None) else None
        self._modifiers = tuple( modifiers or () )
        self._delta = int(delta)
    
    @property
    def pos(self):
        """ Tuple with two integers representing the position of the
        mouse (in screen coordinates).
        """
        return self._pos
    
    @property
    def button(self):
        """ The button that this event applies to (can be None).
        Left=1, right=2, middle=3.
        """
        return self._button
    
    @property
    def modifiers(self):
        """ Tuple that specifies which modifier keys were pressed down at the
        time of the event (shift, control, alt).
        """
        return self._modifiers
    
    @property
    def delta(self):
        """ Integer that represents the amount of scrolling.
        """
        return self._delta


class KeyEvent(Event):
    """ Class describing mouse events.
    
    Input arguments
    ---------------
    type : str
        String indicating the event type (e.g. mouse_press, key_release)
    key : int
        The id of the key in question.
    text : str
        The text representation of the key (can be an empty string).
    modifiers : sequence of ints (optional)
        Which modifier keys were pressed down at the time of the event
        (shift, control, alt).
    """
    
    def __init__(self, type, key=0, text='', modifiers=None):
        Event.__init__(self, type)
        self._key = int(key)
        self._text = str(text) 
        self._modifiers = tuple( modifiers or () )
    
    @property
    def key(self):
        """ Integer that represents the id of the key.
        """
        return self._key
    
    @property
    def text(self):
        """ The text representation of the key (can be an empty string).
        """
        return self._text
    
    @property
    def modifiers(self):
        """ Tuple that specifies which modifier keys were pressed down at the
        time of the event (shift, control, alt).
        """
        return self._modifiers



class EventEmitter(object):
    """Encapsulates a list of event callbacks. 
    
    Each instance of EventEmitter represents the source of a stream of similar
    events, such as mouse click events or timer activation events. For
    example, the following diagram shows the propagation of a mouse click
    event to the list of callbacks that are registered to listen for that event::
    
    
       User clicks    |Canvas creates             |Canvas invokes its                  |EventEmitter invokes 
       mouse on       |MouseEvent:                |'mouse_press' EventEmitter:         |callbacks in sequence:
       Canvas         |                           |                                    |
                   -->|event = MouseEvent(...) -->|Canvas.events.mouse_press(event) -->|callback1(event)
                      |                           |                                 -->|callback2(event)
                      |                           |                                 -->|callback3(event)
    
    Callback functions may be added or removed from an EventEmitter using 
    :func:`connect() <vispy.event.EventEmitter.connect>` or 
    :func:`disconnect() <vispy.event.EventEmitter.disconnect>`. 
    
    Calling an instance of EventEmitter will cause each of its callbacks 
    to be invoked in sequence. All callbacks are invoked with a single
    argument which will be an instance of :class:`Event <vispy.event.Event>`. 
    
    EventEmitters are generally created by an EmitterGroup instance. 
    
    Input arguments
    ---------------
    source : object
        The object that the generated events apply to.
    type : str
        String indicating the event type (e.g. mouse_press, key_release)
    event_class : subclass of Event
        The class of events that this emitter will generate.
    
    """
    def __init__(self, source, type, event_class=Event):
        self.callbacks = []
        self.blocked = 0
        
        self._source = source # todo: should probably be a weakref
        self._type = type
        self.event_class = event_class
        
        #self._defaults = {}
        #self.defaults.update(**kwds)
    
#     @property
#     def defaults(self):
#         """Dictionary containing default attributes to apply to all Events that
#         are sent through this emitter."""
#         return self._defaults
    
    def connect(self, callback):
        """Connect this emitter to a new callback. 
        
        *callback* may be either a callable object or a tuple 
        (object, attr_name) where object.attr_name will point to a callable
        object.
        
        If the callback is already connected, then the request is ignored.
        
        The new callback will be added to the beginning of the callback list; 
        thus the callback that is connected _last_ will be the _first_ to 
        receive events from the emitter.
        """
        if callback in self.callbacks:
            return
        self.callbacks.insert(0, callback)
        return callback  ## allows connect to be used as a decorator
    
    def disconnect(self, callback=None):
        """Disconnect a callback from this emitter.
        
        If no callback is specified, then _all_ callbacks are removed.
        If the callback was not already connected, then the call does nothing.
        """
        if callback is None:
            self.callbacks = []
        else:
            try:
                self.callbacks.remove(callback)
            except ValueError:
                pass
            
    def __call__(self, *args, **kwds):
        """ __call__(**kwds)
        Invoke all callbacks for this emitter.
        
        Emit a new event object, created with the given keyword
        arguments, which must match with the input arguments of the
        corresponding event class. Note that the 'type' argument is
        filled in by the emitter.
        
        Alternatively, the emitter can also be called with an event
        instance as only argument. This allows routing events from one
        emitter to another.
        
        Note that the same Event instance is sent to all callbacks.
        This allows some level of communication between the callbacks
        (notably, via Event.handled) but also requires that callbacks
        be careful not to inadvertently modify the Event. 
        """
        if len(args) == 1 and not kwds and isinstance(args[0], Event):
            event = args[0]
            
            # Ensure that the given event matches what we want to emit
            assert isinstance(event, self.event_class)
            
#             # Copy default attributes onto this event (unless they are already 
#             # specified)
#             for k,v in self.defaults.items():
#                 if not hasattr(event, k):
#                     setattr(event, k, v)
        elif not args:
            event = self.event_class(self._type, **kwds)
#             # merge keyword arguments with defaults before creating event instance
#             kwds2 = self.defaults.copy()
#             kwds2.update(kwds)
#             event = self.event_class(*args, **kwds2)
            
        else:
            raise ValueError("Event emitters can be called with an Event instance or with keyword arguments only.")
        
        # Add our source to the event
        event.sources.append(self._source)
        
        if self.blocked > 0:
            return event
        
        for cb in self.callbacks:
            if isinstance(cb, tuple):
                cb = getattr(cb[0], cb[1], None)
                if cb is None:
                    continue
                
            cb(event)
            if event.blocked:
                break
        
        return event
    
    def block(self):
        """Block this emitter. Any attempts to emit an event while blocked
        will be silently ignored. 
        
        Calls to block are cumulative; the emitter must be unblocked the same
        number of times as it is blocked. 
        """
        self.blocked += 1
        
    def unblock(self):
        """ Unblock this emitter. See :func:`event.EventEmitter.block`.
        """
        self.blocked = max(0, self.blocked-1)

    def blocker(self):
        """Return an EventBlocker to be used in 'with' statements::
        
               with emitter.blocker():
                   ..do stuff; no events will be emitted..
        
        """
        return EventBlocker(self)


class EmitterGroup(EventEmitter):
    """EmitterGroup instances manage a set of related 
    :class:`EventEmitters <vispy.event.EventEmitter>`. 
    Its primary purpose is to provide organization for objects
    that make use of multiple emitters and to reduce the boilerplate code needed
    to initialize those emitters with default connections.
    
    EmitterGroup instances are usually stored as an 'events' attribute on 
    objects that use multiple emitters. For example::
                     
         EmitterGroup  EventEmitter
                 |       |
        Canvas.events.mouse_press
        Canvas.events.resized
        Canvas.events.key_press
    
    EmitterGroup is also a subclass of 
    :class:`EventEmitters <vispy.event.EventEmitter>`, 
    allowing it to emit its own
    events. Any callback that connects directly to the EmitterGroup will 
    receive _all_ of the events generated by the group's emitters.
    
    Input arguments
    ---------------
    source : object
        The object that the generated events apply to.  
    auto_connect : bool
        If *auto_connect* is True (default), then one connection will
        be made for each emitter that looks like 
        :func:`emitter.connect((source, 'on_'+event_name)) 
        <vispy.event.EventEmitter.connect>`.
        This provides a simple mechanism for automatically connecting a large
        group of emitters to default callbacks.
    emitters : keyword arguments
        See the :func:`add <vispy.event.EmitterGroup.add>` method.
    
    """
    
    # todo: with emitters being so simple, I think we can remove the docs below
    """
    Example
    -------
    ::
        
            source = SomeObject()
            source.events = EmitterGroup(source,
                                wheel=Evene,
                                stylus=MyStylusEmitter(source)
                                )
                                
        The example above does the following:
        
            #. Create an EmitterGroup instance
            #. Add four 
               :class:`EventEmitters <vispy.event.EventEmitter>`
               to the group with the names 'mouse', 'key', 'wheel', 
               and 'stylus'.
            #. The first three emitters are all instances of 
               :class:`EventEmitter <vispy.event.EventEmitter>`,
               whereas the last is an instance of MyStylusEmitter.
            #. The four emitters are automatically connected to default 
               callbacks: source.on_mouse, source.on_key, source.on_wheel, and
               source.on_stylus. These connections are symbolic, so source
               is not required to have the callbacks implemented.
    
    """
    def __init__(self, source=None, auto_connect=True, **emitters):
        EventEmitter.__init__(self, source, '')
        
        self.source = source
        self.auto_connect = auto_connect
        self.auto_connect_format = "on_%s"
        self._emitters = collections.OrderedDict()
        self._emitters_connected = False  # whether the sub-emitters have 
                                          # been connected to the group
                                          
        self.add(**emitters)
    
    def __getitem__(self, name):
        """
        Return the emitter assigned to the specified name. 
        Note that emitters may also be retrieved as an attribute of the 
        EmitterGroup.
        """
        return self._emitters[name]
        
    def __setitem__(self, name, emitter):
        """
        Alias for EmitterGroup.add(name=emitter)
        """
        self.add(**{name: emitter})
    
    # todo: disallow passing EventEmitter instances? The use case for which they were allowed can be solved in other ways.
    def add(self, auto_connect=None, **kwds):
        """ Add one or more EventEmitter instances to this emitter group.
        Each keyword argument may be specified as either an EventEmitter 
        instance or an Event subclass, in which case an EventEmitter will be 
        generated automatically. Thus::
        
            # This statement: 
            group.add(mouse_press=MouseEvent, 
                      mouse_release=MouseEvent)
            
            # ..is equivalent to this statement:
            group.add(mouse_press=EventEmitter(source, 'mouse_press', MouseEvent), 
                      mouse_release=EventEmitter(source, 'mouse_press', MouseEvent))
        """
        if auto_connect is None:
            auto_connect = self.auto_connect
        
        # check all names before adding anything
        for name in kwds:
            if name in self._emitters:
                raise ValueError("EmitterGroup already has an emitter named '%s'" % name)
            elif hasattr(self, name):
                raise ValueError("The name '%s' cannot be used as an emitter; it is already an attribute of EmitterGroup" % name)
            
        # add each emitter specified in the keyword arguments
        for name, emitter in kwds.items():
            if emitter is None:
                emitter = Event
            
            if inspect.isclass(emitter) and issubclass(emitter, Event):
                emitter = EventEmitter(self._source, name, emitter)
            elif not isinstance(emitter, EventEmitter):
                raise Exception('Emitter must be specified as either an EventEmitter instance or Event subclass')
            
#             emitter.defaults['name'] = name
#             emitter.defaults['source'] = self.source
            
            setattr(self, name, emitter)
            self._emitters[name] = emitter
            
            if auto_connect:
                emitter.connect((self.source, self.auto_connect_format % name))
                
            # If emitters are connected to the group already, then this one should
            # be connected as well.
            if self._emitters_connected:
                emitter.connect(self)
                
       

    @property
    def emitters(self):
        """ List of current emitters in this group.
        """
        return self._emitters
    
    def __iter__(self):
        """
        Iterates over the names of emitters in this group.
        """
        for k in self._emitters:
            yield k
    
    def block_all(self):
        """ Block all emitters in this group.
        """
        for em in self._emitters.values():
            em.block()
    
    def unblock_all(self):
        """ Unblock all emitters in this group.
        """
        for em in self._emitters.values():
            em.unblock()
    
    ## don't think this is needed anymore.
    #def disconnect_all(self, callback=None):
        #""" Disconnect the given callback from all event emitters in this group.
        #"""
        #for em in self._emitters.values():
            #em.disconnect(callback)
    
    #def blocker(self):
        #return EventBlocker(self)

    def connect(self, *args, **kwds):
        """ Connect the callback to the event group. The callback will receive
        events from _all_ of the emitters in the group.
        
        See :func:`EventEmitter.connect() <vispy.event.EventEmitter.connect>` for
        arguments.
        """
        self._connect_emitters(True)
        return EventEmitter.connect(self, *args, **kwds)

    def disconnect(self, *args, **kwds):
        """ Disconnect the callback from this group. See 
        :func:`connect() <vispy.event.EmitterGroup.connect>` and 
        :func:`EventEmitter.connect() <vispy.event.EventEmitter.connect>` for
        more information.
        """
        ret = EventEmitter.disconnect(self, *args, **kwds)
        if len(self.connections) == 0:
            self._connect_emitters(False)
        return ret
    
    def _connect_emitters(self, connect):
        # Connect/disconnect all sub-emitters from the group. This allows the
        # group to emit an event whenever _any_ of the sub-emitters emit, 
        # while simultaneously eliminating the overhead if nobody is listening.
        if connect:
            for emitter in self:
                self[emitter].connect(self)
        else:
            for emitter in self:
                self[emitter].disconnect(self)
            
        self._emitters_connected = connect
        
            
class EventBlocker(object):
    """ Represents a block for an EventEmitter to be used in a context
    manager (i.e. with statement).
    """
    def __init__(self, target):
        self.target = target
        
    def __enter__(self):
        self.target.block()
        
    def __exit__(self, *args):
        self.target.unblock()
