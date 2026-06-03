import { ArgsType, InputType, Field } from "@nestjs/graphql";
import {
  IsInt,
  IsString,
  Max,
  Min,
  MinLength,
  MaxLength,
  IsOptional,
} from "class-validator";
import { Type } from "class-transformer";

@InputType()
export class SearchTrialInput {
  @IsString()
  @MinLength(10)
  @MaxLength(500)
  @Field(() => String)
  q!: string;
}
