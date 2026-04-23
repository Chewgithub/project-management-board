import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  it("renders five columns", () => {
    render(<KanbanBoard board={initialData} onBoardChange={() => {}} />);
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("emits board updates when renaming a column", async () => {
    const onBoardChange = vi.fn();
    render(<KanbanBoard board={initialData} onBoardChange={onBoardChange} />);

    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    fireEvent.change(input, { target: { value: "New Name" } });

    const latestBoard = onBoardChange.mock.calls.at(-1)?.[0];
    expect(latestBoard.columns[0].title).toBe("New Name");
  });

  it("emits board updates when adding and deleting cards", async () => {
    const onBoardChange = vi.fn();
    render(<KanbanBoard board={initialData} onBoardChange={onBoardChange} />);

    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /save card/i }));

    const afterAdd = onBoardChange.mock.calls.at(-1)?.[0];
    const addedCard = Object.values(afterAdd.cards).find((card) => card.title === "New card");
    expect(addedCard).toBeDefined();

    const deleteButton = within(column).getByRole("button", {
      name: /delete align roadmap themes/i,
    });
    await userEvent.click(deleteButton);

    const afterDelete = onBoardChange.mock.calls.at(-1)?.[0];
    expect(afterDelete.cards["card-1"]).toBeUndefined();
  });
});
