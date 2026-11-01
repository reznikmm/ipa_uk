--  SPDX-FileCopyrightText: 2026 Max Reznik <reznikmm@gmail.com>
--
--  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
------------------------------------------------------------------

--  Reads words (one per line, UTF-8) and prints their transcription,
--  or "<error>" when Transcribe fails.

with Ada.Wide_Wide_Text_IO;

with Ukrainian_IPA;

procedure Transcribe_Words is
   Output  : Wide_Wide_String (1 .. 256);
   Last    : Natural;
   Success : Boolean;
begin
   while not Ada.Wide_Wide_Text_IO.End_Of_File loop
      declare
         Word : constant Wide_Wide_String := Ada.Wide_Wide_Text_IO.Get_Line;
      begin
         Ukrainian_IPA.Transcribe (Word, Output, Last, Success);

         if Success then
            Ada.Wide_Wide_Text_IO.Put_Line (Output (1 .. Last));
         else
            Ada.Wide_Wide_Text_IO.Put_Line ("<error>");
         end if;
      end;
   end loop;
end Transcribe_Words;
