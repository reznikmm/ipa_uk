--  SPDX-FileCopyrightText: 2026 Max Reznik <reznikmm@gmail.com>
--
--  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
------------------------------------------------------------------

with Ada.Wide_Wide_Characters.Handling;

with Ukrainian_IPA.Tables;

package body Ukrainian_IPA is

   use Ukrainian_IPA.Tables;

   Maximum_Expansion : constant := 8;
   --  How many symbols a stage may produce per input symbol, on average

   subtype Buffer_Index is Positive
     range 1 .. Maximum_Word_Length * Maximum_Expansion;

   type Symbol_Buffer is array (Buffer_Index) of Symbol_Index;

   function Find_Symbol (Value : Wide_Wide_Character) return Symbol_Index;
   --  Binary search in Symbols, 0 when Value is not there

   procedure Run_Stage
     (Stage       : Stage_Index;
      Input       : Symbol_Buffer;
      Input_Last  : Natural;
      Output      : out Symbol_Buffer;
      Output_Last : out Natural;
      Success     : out Boolean);

   -----------------
   -- Find_Symbol --
   -----------------

   function Find_Symbol (Value : Wide_Wide_Character) return Symbol_Index is
      Low  : Natural := Natural (Symbols'First);
      High : Natural := Natural (Symbols'Last);
   begin
      while Low <= High loop
         declare
            Middle : constant Natural := (Low + High) / 2;
            Symbol : constant Wide_Wide_Character :=
              Symbols (Symbol_Index (Middle));
         begin
            if Symbol = Value then
               return Symbol_Index (Middle);
            elsif Symbol < Value then
               Low := Middle + 1;
            else
               High := Middle - 1;
            end if;
         end;
      end loop;

      return 0;
   end Find_Symbol;

   ---------------
   -- Run_Stage --
   ---------------

   procedure Run_Stage
     (Stage       : Stage_Index;
      Input       : Symbol_Buffer;
      Input_Last  : Natural;
      Output      : out Symbol_Buffer;
      Output_Last : out Natural;
      Success     : out Boolean)
   is
      State : State_Index := 1;

      procedure Append (Text : Output_Index);
      --  Append the output text to Output, set Success to False on overflow

      procedure Step (Symbol : Symbol_Index);

      ------------
      -- Append --
      ------------

      procedure Append (Text : Output_Index) is
         First : constant Positive := Output_Start (Positive (Text));
         Last  : constant Natural := Output_Start (Positive (Text) + 1) - 1;
      begin
         if Output_Last + Last - First + 1 > Buffer_Index'Last then
            Success := False;
            return;
         end if;

         for Index in First .. Last loop
            Output_Last := Output_Last + 1;
            Output (Output_Last) := Output_Symbols (Index);
         end loop;
      end Append;

      ----------
      -- Step --
      ----------

      procedure Step (Symbol : Symbol_Index) is
         Class      : constant Class_Index := Class_Of (Stage, Symbol);
         Transition : Positive;
      begin
         if Class = 0 then
            Success := False;
            return;
         end if;

         Transition := Transition_Offset (Stage)
           + (Natural (State) - 1) * Natural (Class_Count (Stage))
           + Natural (Class);

         if Next_State (Transition) = 0 then
            Success := False;
            return;
         end if;

         Append (Transition_Output (Transition));
         State := Next_State (Transition);
      end Step;

   begin
      Output_Last := 0;
      Success := True;

      case Direction (Stage) is
         when Left_To_Right =>
            for Index in 1 .. Input_Last loop
               Step (Input (Index));
               exit when not Success;
            end loop;

         when Right_To_Left =>
            for Index in reverse 1 .. Input_Last loop
               Step (Input (Index));
               exit when not Success;
            end loop;
      end case;

      if not Success then
         return;
      end if;

      declare
         Final : constant Output_Index :=
           Final_Output (State_Offset (Stage) + Natural (State));
      begin
         if Final = 0 then
            Success := False;
            return;
         end if;

         Append (Final);
      end;

      if Success and Direction (Stage) = Right_To_Left then
         --  The reversed transducer wrote the text backwards
         for Index in 1 .. Output_Last / 2 loop
            declare
               Saved : constant Symbol_Index := Output (Index);
            begin
               Output (Index) := Output (Output_Last - Index + 1);
               Output (Output_Last - Index + 1) := Saved;
            end;
         end loop;
      end if;
   end Run_Stage;

   ----------------
   -- Transcribe --
   ----------------

   procedure Transcribe
     (Word    : Wide_Wide_String;
      Output  : out Wide_Wide_String;
      Last    : out Natural;
      Success : out Boolean)
   is
      Lower_Word : constant Wide_Wide_String :=
        Ada.Wide_Wide_Characters.Handling.To_Lower (Word);
      Buffers : array (Boolean) of Symbol_Buffer;
      Lasts   : array (Boolean) of Natural := [others => 0];
      Current : Boolean := False;
   begin
      Last := Output'First - 1;
      Success := False;

      if Lower_Word'Length > Maximum_Word_Length then
         return;
      end if;

      for Character of Lower_Word loop
         Lasts (Current) := Lasts (Current) + 1;
         Buffers (Current) (Lasts (Current)) := Find_Symbol (Character);

         if Buffers (Current) (Lasts (Current)) = 0 then
            return;
         end if;
      end loop;

      for Stage in Stage_Index loop
         Run_Stage
           (Stage       => Stage,
            Input       => Buffers (Current),
            Input_Last  => Lasts (Current),
            Output      => Buffers (not Current),
            Output_Last => Lasts (not Current),
            Success     => Success);

         if not Success then
            return;
         end if;

         Current := not Current;
      end loop;

      if Lasts (Current) > Output'Length then
         Success := False;
         return;
      end if;

      for Index in 1 .. Lasts (Current) loop
         Last := Last + 1;
         Output (Last) := Symbols (Buffers (Current) (Index));
      end loop;
   end Transcribe;

end Ukrainian_IPA;
