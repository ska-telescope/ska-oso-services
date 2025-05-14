.. _prsl:

Creating Proposals 
===================

TODO: add a sequence diagram for the prsl api

.. uml::

   @startuml
   actor Client
   participant API
   database DB

   Client -> API: POST /proposals
   API -> DB: INSERT
   DB --> API: ID
   API --> Client: 201 Created
   @enduml
