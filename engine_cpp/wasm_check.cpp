#include "engine.hpp"
extern "C" void engine_turn(loong::Game* g, loong::Action const* a) { loong::Act(*g,*a); }
