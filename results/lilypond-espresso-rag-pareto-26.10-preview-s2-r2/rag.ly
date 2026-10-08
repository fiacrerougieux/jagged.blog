\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = \markup \italic "for café piano"
}

global = { \key c \major \time 2/4 }

upper = {
  \tempo "Allegretto" 4 = 92
  \global
  \clef treble
  % ---- A strain, bars 1-4 ----
  c''8.\mf e''16 g''8 e''16 g''16 |
  a''8. g''16 e''8 c''8 |
  f''8. e''16 d''8 f''8 |
  g'16 c''16 e''16 g''16 c''4~ |
  \break
  % ---- bars 5-8 ----
  c''8. e''16 g''8 e''16 g''16 |
  a''8. b''16 c'''8 a''16 c'''16 |
  d'''8. c'''16 a''8 f''8 |
  c'''16 g''8. e''4 |
  \break
  % ---- B strain, bars 9-12: left hand crosses over the right ----
  \mark \markup \italic "L.H. crosses over R.H."
  <<
    { g'8\mp_\markup \small \italic "R.H." <c'' e''>8 g'8 <c'' e''>8 |
      a'8 <d'' f''>8 a'8 <d'' f''>8 |
      g'8 <c'' e''>8 g'8 <c'' e''>8 |
      b'8 <d'' f''>8 b'8 <d'' f''>8 } \\
    { c'''4^\markup { \bold \italic "L.H." } e'''8 f'''8 |
      g'''4 f'''8 d'''8 |
      e'''4 c'''8 e'''8 |
      b''8 d'''8 f'''8 d'''8 }
  >>
  \break
  % ---- A strain return, bars 13-16 ----
  c''8.\mf e''16 g''8 e''16 g''16 |
  a''8. g''16 e''8 c''8 |
  g''8. f''16 d''8 b'8 |
  c''4 r4 |
  \bar "|."
}

lower = {
  \global
  \clef bass
  % ---- oom-pah bass, bars 1-8 ----
  c,8 <e g>8 g,8 <e g>8 |
  c,8 <e g>8 g,8 <e g>8 |
  g,8 <d f>8 b,8 <d f>8 |
  c,8 <e g>8 g,8 <e g>8 |
  c,8 <e g>8 g,8 <e g>8 |
  f,8 <a c>8 c8 <a c>8 |
  g,8 <d f>8 b,8 <d f>8 |
  c,8 <e g c'>8 g,8 <e g c'>8 |
  % ---- bars 9-12: bass staff rests while the left hand is up top ----
  R2*4 |
  % ---- bars 13-16 ----
  c,8 <e g>8 g,8 <e g>8 |
  c,8 <e g>8 g,8 <e g>8 |
  g,8 <d f>8 b,8 <d f>8 |
  c,4 <e g c'>4 |
}

\score {
  \new PianoStaff <<
    \new Staff = "up" \upper
    \new Staff = "down" \lower
  >>
  \layout {
    \context {
      \Score
      barNumberVisibility = #all-bar-numbers-visible
    }
  }
  \midi { }
}
